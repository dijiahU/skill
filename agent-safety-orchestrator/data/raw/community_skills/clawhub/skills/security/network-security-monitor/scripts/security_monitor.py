"""
OpenClaw Security Monitor Plugin
安全监控插件 - 监控网络访问和文件下载，检查威胁情报
Security monitoring plugin - Monitors network access and file downloads, checks threat intelligence
"""

import os
import sys
import json
import hashlib
import re
import logging
import time
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from urllib.parse import urlparse


class LRUCache:
    """LRU缓存实现 / LRU Cache Implementation"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl
        self.timestamps = {}
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项 / Get cache item"""
        if key not in self.cache:
            return None
        
        if datetime.now().timestamp() - self.timestamps.get(key, 0) > self.ttl:
            del self.cache[key]
            del self.timestamps[key]
            return None
        
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def set(self, key: str, value: Any):
        """设置缓存项 / Set cache item"""
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
        
        self.cache[key] = value
        self.timestamps[key] = datetime.now().timestamp()
    
    def delete(self, key: str):
        """删除缓存项 / Delete cache item"""
        if key in self.cache:
            del self.cache[key]
            del self.timestamps[key]
    
    def clear(self):
        """清空缓存 / Clear cache"""
        self.cache.clear()
        self.timestamps.clear()
    
    def get_info(self) -> Dict:
        """获取缓存信息 / Get cache info"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'ttl': self.ttl,
            'keys': list(self.cache.keys())[:100]
        }
    
    def __contains__(self, key: str) -> bool:
        return key in self.cache


class SecurityMonitor:
    """安全监控主类 / Security Monitor Main Class"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self.load_config(config_path)
        self.setup_logging()
        
        cache_config = self.config.get('cache', {})
        self.cache = LRUCache(
            max_size=cache_config.get('max_size', 1000),
            ttl=cache_config.get('ttl', 3600)
        )
        
        self.stats = {
            'total_checks': 0,
            'blocked': 0,
            'warned': 0,
            'logged': 0,
            'benign': 0,
            'threat_types': {},
            'api_calls': 0,
            'api_latencies': [],
            'ioc_queries': {
                'ip': 0,
                'domain': 0,
                'url': 0,
                'file': 0
            },
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        self.api_latency_stats = {
            'min': float('inf'),
            'max': 0,
            'sum': 0,
            'count': 0
        }
        
        self.hs_ti_available = self.check_hs_ti_availability()
    
    def load_config(self, config_path: Optional[str] = None) -> Dict:
        """加载配置文件 / Load configuration file"""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
        
        default_config = {
            "threat_intel": {
                "provider": "hs-ti",
                "enabled": True,
                "cache_ttl": 3600,
                "timeout": 5000,
                "fallback_to_custom": False,
                "custom_api": {
                    "api_url": "https://ti.hillstonenet.com.cn",
                    "api_key": os.environ.get('SECURITY_MONITOR_API_KEY', '')
                }
            },
            "cache": {
                "enabled": True,
                "max_size": 1000,
                "ttl": 3600
            },
            "policy": {
                "block_critical": True,
                "block_high": False,
                "warn_high": True,
                "warn_medium": True,
                "log_low": True,
                "log_benign": False,
                "require_confirmation": True
            },
            "whitelist": {
                "enabled": True,
                "domains": ["github.com", "openclaw.ai", "hillstonenet.com.cn"],
                "ips": [],
                "patterns": []
            },
            "blacklist": {
                "enabled": True,
                "domains": [],
                "ips": [],
                "patterns": []
            },
            "logging": {
                "enabled": True,
                "log_file": "~/.openclaw/logs/security-monitor.log",
                "log_blocked": True,
                "log_warned": True,
                "log_logged": True,
                "log_benign": False
            },
            "monitoring": {
                "web_fetch": True,
                "web_search": True,
                "browser": True,
                "file_download": True,
                "check_file_hashes": True
            },
            "language": "auto"
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                self.log(f"配置文件加载失败: {e}", level="ERROR")
        
        return default_config
    
    def setup_logging(self):
        """设置日志 / Setup logging"""
        log_file = os.path.expanduser(self.config['logging']['log_file'])
        log_dir = os.path.dirname(log_file)
        
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log(self, message: str, level: str = "INFO"):
        """记录日志 / Log message"""
        if not self.config['logging']['enabled']:
            return
        
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        mask_patterns = [
            r'api_key["\']?\s*[:=]\s*["\']?[^"\']{8,}["\']?',
            r'X-Auth-Token["\']?\s*[:=]\s*["\']?[^"\']{8,}["\']?',
            r'key["\']?\s*[:=]\s*["\']?[^"\']{8,}["\']?'
        ]
        
        masked_message = message
        for pattern in mask_patterns:
            masked_message = re.sub(pattern, '[REDACTED]', masked_message, flags=re.IGNORECASE)
        
        self.logger.log(log_level, masked_message)
    
    def check_hs_ti_availability(self) -> bool:
        """检查hs-ti技能是否可用 / Check if hs-ti skill is available"""
        try:
            skills_dir = Path(os.path.dirname(__file__)).parent.parent
            hs_ti_path = skills_dir / "hs-ti" / "scripts" / "hs_ti_plugin.py"
            
            if hs_ti_path.exists():
                self.log("检测到hs-ti技能 / Detected hs-ti skill", level="INFO")
                return True
            
            self.log("未检测到hs-ti技能 / hs-ti skill not detected", level="WARNING")
            return False
        except Exception as e:
            self.log(f"检查hs-ti可用性失败: {e}", level="ERROR")
            return False
    
    def extract_targets(self, params: Dict, tool_name: str) -> List[Dict]:
        """从工具参数中提取目标 / Extract targets from tool parameters"""
        targets = []
        
        if tool_name in ['web_fetch', 'web_search']:
            url = params.get('url', '')
            if url:
                targets.append({
                    'type': 'url',
                    'value': url,
                    'domain': self.extract_domain(url)
                })
        
        elif tool_name == 'browser':
            url = params.get('url', '')
            if url:
                targets.append({
                    'type': 'url',
                    'value': url,
                    'domain': self.extract_domain(url)
                })
        
        elif tool_name == 'file_download':
            file_path = params.get('path', '')
            if file_path and os.path.exists(file_path):
                file_hash = self.calculate_file_hash(file_path)
                targets.append({
                    'type': 'file',
                    'value': file_hash,
                    'path': file_path
                })
        
        return targets
    
    def extract_domain(self, url: str) -> Optional[str]:
        """从URL中提取域名 / Extract domain from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if ':' in domain:
                domain = domain.split(':')[0]
            
            if not domain:
                return None
            
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', domain):
                return None
            
            return domain
        except Exception:
            return None
    
    def calculate_file_hash(self, file_path: str, algorithm: str = 'sha256') -> str:
        """计算文件哈希 / Calculate file hash"""
        try:
            hash_func = getattr(hashlib, algorithm)()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            self.log(f"计算文件哈希失败: {e}", level="ERROR")
            return ""
    
    def check_whitelist(self, target: Dict) -> bool:
        """检查白名单 / Check whitelist"""
        if not self.config['whitelist']['enabled']:
            return False
        
        whitelist = self.config['whitelist']
        
        if target['type'] == 'url' and 'domain' in target:
            domain = target['domain']
            if domain in whitelist.get('domains', []):
                self.log(f"域名在白名单中: {domain}", level="INFO")
                return True
        
        if target['type'] == 'ip':
            if target['value'] in whitelist.get('ips', []):
                self.log(f"IP在白名单中: {target['value']}", level="INFO")
                return True
        
        return False
    
    def check_blacklist(self, target: Dict) -> bool:
        """检查黑名单 / Check blacklist"""
        if not self.config['blacklist']['enabled']:
            return False
        
        blacklist = self.config['blacklist']
        
        if target['type'] == 'url' and 'domain' in target:
            domain = target['domain']
            if domain in blacklist.get('domains', []):
                self.log(f"域名在黑名单中: {domain}", level="WARNING")
                return True
        
        if target['type'] == 'ip':
            if target['value'] in blacklist.get('ips', []):
                self.log(f"IP在黑名单中: {target['value']}", level="WARNING")
                return True
        
        return False
    
    def query_threat_intel(self, target: Dict) -> Optional[Dict]:
        """查询威胁情报 / Query threat intelligence"""
        if not self.config['threat_intel']['enabled']:
            return None
        
        self.stats['ioc_queries'][target['type']] = self.stats['ioc_queries'].get(target['type'], 0) + 1
        
        cache_key = f"{target['type']}:{target['value']}"
        
        if self.config['cache'].get('enabled', True):
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                self.stats['cache_hits'] += 1
                return cached_result
            self.stats['cache_misses'] += 1
        
        start_time = time.time()
        threat_info = None
        
        if self.hs_ti_available:
            threat_info = self.query_hs_ti(target)
        elif self.config['threat_intel']['fallback_to_custom']:
            threat_info = self.query_custom_api(target)
        else:
            self.log("未配置威胁情报源，建议安装hs-ti技能", level="WARNING")
            self.log("No threat intelligence source configured. Please install hs-ti skill.", level="WARNING")
            self.log("hs-ti技能地址: https://clawhub.ai/maxjia/hs-ti", level="INFO")
            self.log("hs-ti skill URL: https://clawhub.ai/maxjia/hs-ti", level="INFO")
            return None
        
        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)
        
        self.stats['api_calls'] += 1
        self.stats['api_latencies'].append(latency_ms)
        self.api_latency_stats['count'] += 1
        self.api_latency_stats['sum'] += latency_ms
        
        if latency_ms < self.api_latency_stats['min']:
            self.api_latency_stats['min'] = latency_ms
        if latency_ms > self.api_latency_stats['max']:
            self.api_latency_stats['max'] = latency_ms
        
        if threat_info and self.config['cache'].get('enabled', True):
            self.cache.set(cache_key, threat_info)
        
        return threat_info
    
    def query_hs_ti(self, target: Dict) -> Optional[Dict]:
        """查询hs-ti威胁情报 / Query hs-ti threat intelligence"""
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hs-ti', 'scripts'))
            from hs_ti_plugin import YunzhanThreatIntel
            
            intel = YunzhanThreatIntel()
            
            if target['type'] == 'ip':
                result = intel.query_ip_reputation(target['value'])
            elif target['type'] == 'domain':
                result = intel.query_domain_reputation(target['value'])
            elif target['type'] == 'url':
                result = intel.query_url_reputation(target['value'])
            elif target['type'] == 'file':
                result = intel.query_file_reputation(target['value'])
            else:
                return None
            
            return self.parse_hs_ti_result(result)
        except Exception as e:
            self.log(f"查询hs-ti失败: {e}", level="ERROR")
            return None
    
    def parse_hs_ti_result(self, result: Dict) -> Optional[Dict]:
        """解析hs-ti查询结果 / Parse hs-ti query result"""
        if not result or 'data' not in result:
            return None
        
        data = result['data']
        
        return {
            'threat_type': data.get('threat_type', 'unknown'),
            'credibility': data.get('credibility', 'unknown'),
            'threat_level': self.assess_threat_level(data),
            'details': data
        }
    
    def query_custom_api(self, target: Dict) -> Optional[Dict]:
        """查询自定义威胁情报API / Query custom threat intelligence API"""
        try:
            import urllib.request
            import urllib.parse
            
            api_config = self.config['threat_intel']['custom_api']
            api_url = api_config['api_url']
            api_key = api_config['api_key']
            
            if not api_key:
                self.log("未配置自定义API密钥", level="WARNING")
                return None
            
            endpoint = self.get_api_endpoint(target['type'])
            url = f"{api_url}{endpoint}?key={target['value']}"
            
            headers = {
                'X-Auth-Token': api_key,
                'Accept': 'application/json'
            }
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.config['threat_intel']['timeout']/1000) as response:
                data = json.loads(response.read().decode('utf-8'))
                return self.parse_custom_result(data)
        except Exception as e:
            self.log(f"查询自定义API失败: {e}", level="ERROR")
            return None
    
    def get_api_endpoint(self, target_type: str) -> str:
        """获取API端点 / Get API endpoint"""
        endpoints = {
            'ip': '/api/ip/reputation',
            'domain': '/api/domain/reputation',
            'url': '/api/url/reputation',
            'file': '/api/file/reputation'
        }
        return endpoints.get(target_type, '')
    
    def parse_custom_result(self, result: Dict) -> Optional[Dict]:
        """解析自定义API结果 / Parse custom API result"""
        if not result or 'data' not in result:
            return None
        
        data = result['data']
        
        return {
            'threat_type': data.get('threat_type', 'unknown'),
            'credibility': data.get('credibility', 'unknown'),
            'threat_level': self.assess_threat_level(data),
            'details': data
        }
    
    def assess_threat_level(self, threat_data: Dict) -> str:
        """评估威胁等级 / Assess threat level"""
        threat_type = threat_data.get('threat_type', '').lower()
        credibility = threat_data.get('credibility', '').lower()
        
        if threat_type in ['malicious', 'malware', 'phishing', 'c2']:
            return 'critical'
        elif threat_type in ['suspicious', 'high_risk']:
            return 'high'
        elif threat_type in ['potential_risk', 'medium_risk']:
            return 'medium'
        elif threat_type in ['low_risk', 'benign']:
            return 'low'
        else:
            return 'benign'
    
    def handle_threat(self, target: Dict, threat_info: Optional[Dict]) -> Dict:
        """处理威胁 / Handle threat"""
        self.stats['total_checks'] += 1
        
        if threat_info is None:
            self.stats['benign'] += 1
            return {'action': 'allow', 'reason': 'no_threat_info'}
        
        threat_level = threat_info['threat_level']
        
        if threat_level == 'critical' and self.config['policy']['block_critical']:
            self.stats['blocked'] += 1
            self.log_security_event(target, threat_info, 'BLOCKED')
            return {
                'action': 'block',
                'reason': 'critical_threat',
                'threat_info': threat_info
            }
        elif threat_level == 'high' and self.config['policy']['block_high']:
            self.stats['blocked'] += 1
            self.log_security_event(target, threat_info, 'BLOCKED')
            return {
                'action': 'block',
                'reason': 'high_threat',
                'threat_info': threat_info
            }
        elif threat_level in ['high', 'medium'] and (
            self.config['policy']['warn_high'] or self.config['policy']['warn_medium']
        ):
            self.stats['warned'] += 1
            self.log_security_event(target, threat_info, 'WARNED')
            return {
                'action': 'warn',
                'reason': f'{threat_level}_threat',
                'threat_info': threat_info
            }
        elif threat_level in ['low', 'benign']:
            self.stats['benign'] += 1
            self.log_security_event(target, threat_info, 'LOGGED')
            return {
                'action': 'log',
                'reason': f'{threat_level}_threat',
                'threat_info': threat_info
            }
        else:
            self.stats['logged'] += 1
            self.log_security_event(target, threat_info, 'LOGGED')
            return {
                'action': 'log',
                'reason': 'low_threat',
                'threat_info': threat_info
            }
    
    def log_security_event(self, target: Dict, threat_info: Dict, action: str):
        """记录安全事件 / Log security event"""
        threat_type = threat_info.get('threat_type', 'unknown')
        self.stats['threat_types'][threat_type] = self.stats['threat_types'].get(threat_type, 0) + 1
        
        log_level = "INFO"
        if action == 'BLOCKED':
            log_level = "WARNING"
        elif action == 'WARNED':
            log_level = "INFO"
        
        message = f"[{action}] {target['value']} - {threat_type} - {threat_info['threat_level'].upper()}"
        self.log(message, level=log_level)
    
    def get_warning_message(self, target: Dict, threat_info: Dict, action: str) -> str:
        """获取警告消息 / Get warning message"""
        language = self.config.get('language', 'auto')
        
        if language == 'auto':
            language = 'zh'
        
        if language == 'zh':
            return self.get_warning_message_zh(target, threat_info, action)
        else:
            return self.get_warning_message_en(target, threat_info, action)
    
    def get_warning_message_zh(self, target: Dict, threat_info: Dict, action: str) -> str:
        """获取中文警告消息 / Get Chinese warning message"""
        threat_type = threat_info.get('threat_type', 'unknown')
        threat_level = threat_info.get('threat_level', 'unknown')
        credibility = threat_info.get('credibility', 'unknown')
        
        if action == 'BLOCKED':
            return f"""
🚨 安全警告 / Security Warning

检测到严重威胁 / Critical threat detected!

目标 / Target: {target['value']}
威胁类型 / Threat Type: {threat_type}
威胁等级 / Threat Level: {threat_level.upper()}
可信度 / Credibility: {credibility}

此访问已被阻止 / This access has been blocked.

建议 / Recommendation:
- 避免访问此网站 / Avoid accessing this website
- 检查是否有恶意软件 / Check for malware
- 如需访问，请手动添加到白名单 / To access, add to whitelist manually
"""
        elif action == 'WARNED':
            return f"""
⚠️ 安全警告 / Security Warning

检测到高风险 / High risk detected!

目标 / Target: {target['value']}
威胁类型 / Threat Type: {threat_type}
威胁等级 / Threat Level: {threat_level.upper()}
可信度 / Credibility: {credibility}

是否继续访问？/ Continue access?

[是 / Yes] - 继续访问（风险自负）/ Continue access (at your own risk)
[否 / No] - 取消访问 / Cancel access
"""
        else:
            return ""
    
    def get_warning_message_en(self, target: Dict, threat_info: Dict, action: str) -> str:
        """获取英文警告消息 / Get English warning message"""
        threat_type = threat_info.get('threat_type', 'unknown')
        threat_level = threat_info.get('threat_level', 'unknown')
        credibility = threat_info.get('credibility', 'unknown')
        
        if action == 'BLOCKED':
            return f"""
🚨 Security Warning

Critical threat detected!

Target: {target['value']}
Threat Type: {threat_type}
Threat Level: {threat_level.upper()}
Credibility: {credibility}

This access has been blocked.

Recommendation:
- Avoid accessing this website
- Check for malware
- To access, add to whitelist manually
"""
        elif action == 'WARNED':
            return f"""
⚠️ Security Warning

High risk detected!

Target: {target['value']}
Threat Type: {threat_type}
Threat Level: {threat_level.upper()}
Credibility: {credibility}

Continue access?

[Yes] - Continue access (at your own risk)
[No] - Cancel access
"""
        else:
            return ""
    
    def get_statistics(self) -> Dict:
        """获取统计信息 / Get statistics"""
        stats = dict(self.stats)
        
        if self.api_latency_stats['count'] > 0:
            stats['api_latency'] = {
                'min': self.api_latency_stats['min'],
                'max': self.api_latency_stats['max'],
                'avg': int(self.api_latency_stats['sum'] / self.api_latency_stats['count']),
                'count': self.api_latency_stats['count']
            }
        else:
            stats['api_latency'] = {
                'min': 0,
                'max': 0,
                'avg': 0,
                'count': 0
            }
        
        if stats['cache_hits'] + stats['cache_misses'] > 0:
            stats['cache_hit_rate'] = round(
                (stats['cache_hits'] / (stats['cache_hits'] + stats['cache_misses'])) * 100,
                2
            )
        else:
            stats['cache_hit_rate'] = 0
        
        stats['cache_info'] = self.cache.get_info()
        
        return stats
    
    def reset_statistics(self):
        """重置统计信息 / Reset statistics"""
        self.stats = {
            'total_checks': 0,
            'blocked': 0,
            'warned': 0,
            'logged': 0,
            'benign': 0,
            'threat_types': {},
            'api_calls': 0,
            'api_latencies': [],
            'ioc_queries': {
                'ip': 0,
                'domain': 0,
                'url': 0,
                'file': 0
            },
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        self.api_latency_stats = {
            'min': float('inf'),
            'max': 0,
            'sum': 0,
            'count': 0
        }
        
        self.log("统计信息已重置 / Statistics have been reset", level="INFO")
    
    def get_cache_info(self) -> Dict:
        """获取缓存信息 / Get cache info"""
        return self.cache.get_info()
    
    def clear_cache(self):
        """清空缓存 / Clear cache"""
        self.cache.clear()
        self.log("缓存已清空 / Cache has been cleared", level="INFO")
    
    def delete_cache_key(self, key: str):
        """删除缓存项 / Delete cache item"""
        self.cache.delete(key)
        self.log(f"缓存项已删除 / Cache item deleted: {key}", level="INFO")


def before_tool_call(tool_name: str, params: Dict) -> Dict:
    """工具调用前钩子 / Before tool call hook"""
    monitor = SecurityMonitor()
    
    if not monitor.config['monitoring'].get(tool_name, False):
        return {'allow': True}
    
    targets = monitor.extract_targets(params, tool_name)
    
    if not targets:
        return {'allow': True}
    
    results = []
    for target in targets:
        if monitor.check_blacklist(target):
            results.append({
                'target': target,
                'action': 'block',
                'reason': 'blacklisted'
            })
            continue
        
        if monitor.check_whitelist(target):
            results.append({
                'target': target,
                'action': 'allow',
                'reason': 'whitelisted'
            })
            continue
        
        threat_info = monitor.query_threat_intel(target)
        result = monitor.handle_threat(target, threat_info)
        results.append({
            'target': target,
            'result': result
        })
    
    blocked_count = sum(1 for r in results if r.get('result', {}).get('action') == 'block')
    
    if blocked_count > 0:
        warning_messages = []
        for r in results:
            if r.get('result', {}).get('action') in ['block', 'warn']:
                warning_messages.append(monitor.get_warning_message(
                    r['target'],
                    r['result'].get('threat_info', {}),
                    r['result'].get('action', '')
                ))
        
        return {
            'allow': False,
            'reason': 'security_block',
            'warnings': warning_messages,
            'results': results
        }
    
    return {
        'allow': True,
        'results': results
    }


def get_security_stats() -> Dict:
    """获取安全统计 / Get security statistics"""
    monitor = SecurityMonitor()
    return monitor.get_statistics()


def reset_security_stats():
    """重置安全统计 / Reset security statistics"""
    monitor = SecurityMonitor()
    monitor.reset_statistics()


def get_cache_info() -> Dict:
    """获取缓存信息 / Get cache info"""
    monitor = SecurityMonitor()
    return monitor.get_cache_info()


def clear_cache():
    """清空缓存 / Clear cache"""
    monitor = SecurityMonitor()
    monitor.clear_cache()


def delete_cache_key(key: str):
    """删除缓存项 / Delete cache item"""
    monitor = SecurityMonitor()
    monitor.delete_cache_key(key)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='OpenClaw Security Monitor')
    parser.add_argument('--check', type=str, help='检查特定目标 / Check specific target')
    parser.add_argument('--stats', action='store_true', help='显示统计信息 / Show statistics')
    parser.add_argument('--reset', action='store_true', help='重置统计 / Reset statistics')
    parser.add_argument('--cache-info', action='store_true', help='显示缓存信息 / Show cache info')
    parser.add_argument('--clear-cache', action='store_true', help='清空缓存 / Clear cache')
    parser.add_argument('--delete-cache', type=str, help='删除缓存项 / Delete cache item')
    parser.add_argument('--api-stats', action='store_true', help='显示API统计 / Show API statistics')
    
    args = parser.parse_args()
    
    monitor = SecurityMonitor()
    
    if args.check:
        target = args.check
        if target.startswith('http://') or target.startswith('https://'):
            target_type = 'url'
        elif re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', target):
            target_type = 'ip'
        else:
            target_type = 'domain'
        
        threat_info = monitor.query_threat_intel({
            'type': target_type,
            'value': target
        })
        
        if threat_info:
            print(f"威胁类型 / Threat Type: {threat_info['threat_type']}")
            print(f"威胁等级 / Threat Level: {threat_info['threat_level'].upper()}")
            print(f"可信度 / Credibility: {threat_info['credibility']}")
        else:
            print("未找到威胁信息 / No threat information found")
    
    elif args.stats:
        stats = monitor.get_statistics()
        print("\n安全统计 / Security Statistics")
        print("=" * 60)
        print(f"总检查次数 / Total Checks: {stats['total_checks']}")
        print(f"阻止访问 / Blocked: {stats['blocked']}")
        print(f"警告访问 / Warned: {stats['warned']}")
        print(f"记录事件 / Logged: {stats['logged']}")
        print(f"良性访问 / Benign: {stats['benign']}")
        
        print("\nIOC查询统计 / IOC Query Statistics")
        print("-" * 60)
        print(f"IP查询 / IP Queries: {stats['ioc_queries']['ip']}")
        print(f"域名查询 / Domain Queries: {stats['ioc_queries']['domain']}")
        print(f"URL查询 / URL Queries: {stats['ioc_queries']['url']}")
        print(f"文件查询 / File Queries: {stats['ioc_queries']['file']}")
        
        print("\nAPI调用统计 / API Call Statistics")
        print("-" * 60)
        print(f"API调用次数 / API Calls: {stats['api_calls']}")
        if stats['api_latency']['count'] > 0:
            print(f"最小延迟 / Min Latency: {stats['api_latency']['min']}ms")
            print(f"最大延迟 / Max Latency: {stats['api_latency']['max']}ms")
            print(f"平均延迟 / Avg Latency: {stats['api_latency']['avg']}ms")
        
        print("\n缓存统计 / Cache Statistics")
        print("-" * 60)
        print(f"缓存命中 / Cache Hits: {stats['cache_hits']}")
        print(f"缓存未命中 / Cache Misses: {stats['cache_misses']}")
        print(f"缓存命中率 / Cache Hit Rate: {stats['cache_hit_rate']}%")
        print(f"缓存大小 / Cache Size: {stats['cache_info']['size']}/{stats['cache_info']['max_size']}")
        
        print("\n威胁类型分布 / Threat Type Distribution:")
        for threat_type, count in stats['threat_types'].items():
            print(f"- {threat_type}: {count}")
    
    elif args.api_stats:
        stats = monitor.get_statistics()
        print("\nAPI调用统计 / API Call Statistics")
        print("=" * 40)
        print(f"API调用次数 / API Calls: {stats['api_calls']}")
        if stats['api_latency']['count'] > 0:
            print(f"最小延迟 / Min Latency: {stats['api_latency']['min']}ms")
            print(f"最大延迟 / Max Latency: {stats['api_latency']['max']}ms")
            print(f"平均延迟 / Avg Latency: {stats['api_latency']['avg']}ms")
            print(f"统计样本 / Sample Count: {stats['api_latency']['count']}")
        else:
            print("暂无API调用记录 / No API calls yet")
    
    elif args.cache_info:
        cache_info = monitor.get_cache_info()
        print("\n缓存信息 / Cache Info")
        print("=" * 40)
        print(f"缓存大小 / Cache Size: {cache_info['size']}/{cache_info['max_size']}")
        print(f"TTL / Time To Live: {cache_info['ttl']}秒 / seconds")
        
        if cache_info['keys']:
            print("\n缓存键（前100个）/ Cache Keys (first 100):")
            for key in cache_info['keys']:
                print(f"- {key}")
        else:
            print("\n缓存为空 / Cache is empty")
    
    elif args.clear_cache:
        monitor.clear_cache()
        print("缓存已清空 / Cache has been cleared")
    
    elif args.delete_cache:
        monitor.delete_cache_key(args.delete_cache)
        print(f"缓存项已删除 / Cache item deleted: {args.delete_cache}")
    
    elif args.reset:
        reset_security_stats()
        print("统计信息已重置 / Statistics have been reset")

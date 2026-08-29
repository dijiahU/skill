"""
Security Monitor Plugin Tests
安全监控插件测试
"""

import unittest
import os
import sys
import json
import tempfile
from unittest.mock import Mock, patch
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
    from security_monitor import SecurityMonitor, before_tool_call, get_security_stats, reset_security_stats
except ImportError as e:
    print(f"导入失败: {e}")
    print(f"当前目录: {os.getcwd()}")
    print(f"脚本目录: {os.path.join(os.path.dirname(__file__), '..', 'scripts')}")
    sys.exit(1)


class TestSecurityMonitor(unittest.TestCase):
    """安全监控测试类 / Security Monitor Test Class"""
    
    def setUp(self):
        """测试设置 / Test setup"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'config.json')
        self.log_path = os.path.join(self.temp_dir, 'security-monitor.log')
        
        self.test_config = {
            "threat_intel": {
                "provider": "hs-ti",
                "enabled": True,
                "cache_ttl": 3600,
                "timeout": 5000,
                "fallback_to_custom": False,
                "custom_api": {
                    "api_url": "https://ti.hillstonenet.com.cn",
                    "api_key": ""
                }
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
                "domains": ["github.com", "openclaw.ai"],
                "ips": [],
                "patterns": []
            },
            "blacklist": {
                "enabled": True,
                "domains": ["malicious-site.com"],
                "ips": ["192.168.1.100"],
                "patterns": []
            },
            "logging": {
                "enabled": True,
                "log_file": self.log_path,
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
            "language": "zh"
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
    
    def tearDown(self):
        """测试清理 / Test cleanup"""
        import shutil
        import logging
        
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
        
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                pass
    
    def test_load_config(self):
        """测试配置加载 / Test config loading"""
        monitor = SecurityMonitor(self.config_path)
        
        self.assertEqual(monitor.config['threat_intel']['provider'], 'hs-ti')
        self.assertTrue(monitor.config['threat_intel']['enabled'])
        self.assertEqual(monitor.config['policy']['block_critical'], True)
        self.assertEqual(monitor.config['whitelist']['domains'], ['github.com', 'openclaw.ai'])
    
    def test_extract_domain(self):
        """测试域名提取 / Test domain extraction"""
        monitor = SecurityMonitor(self.config_path)
        
        test_cases = [
            ('https://example.com/path', 'example.com'),
            ('http://sub.example.com', 'sub.example.com'),
            ('https://example.com:8080/path', 'example.com'),
            ('http://192.168.1.1', None),
            ('invalid-url', None)
        ]
        
        for url, expected_domain in test_cases:
            result = monitor.extract_domain(url)
            self.assertEqual(result, expected_domain)
    
    def test_calculate_file_hash(self):
        """测试文件哈希计算 / Test file hash calculation"""
        monitor = SecurityMonitor(self.config_path)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write('test content')
            f.flush()
            temp_path = f.name
        
        try:
            hash_sha256 = monitor.calculate_file_hash(temp_path, 'sha256')
            hash_md5 = monitor.calculate_file_hash(temp_path, 'md5')
            
            self.assertEqual(len(hash_sha256), 64)
            self.assertEqual(len(hash_md5), 32)
            self.assertNotEqual(hash_sha256, hash_md5)
        finally:
            os.unlink(temp_path)
    
    def test_check_whitelist(self):
        """测试白名单检查 / Test whitelist check"""
        monitor = SecurityMonitor(self.config_path)
        
        whitelisted_domain = {
            'type': 'url',
            'value': 'https://github.com/test',
            'domain': 'github.com'
        }
        
        not_whitelisted_domain = {
            'type': 'url',
            'value': 'https://example.com/test',
            'domain': 'example.com'
        }
        
        self.assertTrue(monitor.check_whitelist(whitelisted_domain))
        self.assertFalse(monitor.check_whitelist(not_whitelisted_domain))
    
    def test_check_blacklist(self):
        """测试黑名单检查 / Test blacklist check"""
        monitor = SecurityMonitor(self.config_path)
        
        blacklisted_domain = {
            'type': 'url',
            'value': 'https://malicious-site.com/test',
            'domain': 'malicious-site.com'
        }
        
        not_blacklisted_domain = {
            'type': 'url',
            'value': 'https://example.com/test',
            'domain': 'example.com'
        }
        
        self.assertTrue(monitor.check_blacklist(blacklisted_domain))
        self.assertFalse(monitor.check_blacklist(not_blacklisted_domain))
    
    def test_extract_targets_web_fetch(self):
        """测试web_fetch目标提取 / Test web_fetch target extraction"""
        monitor = SecurityMonitor(self.config_path)
        
        params = {'url': 'https://example.com'}
        targets = monitor.extract_targets(params, 'web_fetch')
        
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['type'], 'url')
        self.assertEqual(targets[0]['value'], 'https://example.com')
        self.assertEqual(targets[0]['domain'], 'example.com')
    
    def test_extract_targets_browser(self):
        """测试browser目标提取 / Test browser target extraction"""
        monitor = SecurityMonitor(self.config_path)
        
        params = {'url': 'https://example.com'}
        targets = monitor.extract_targets(params, 'browser')
        
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['type'], 'url')
    
    def test_assess_threat_level(self):
        """测试威胁等级评估 / Test threat level assessment"""
        monitor = SecurityMonitor(self.config_path)
        
        test_cases = [
            ({'threat_type': 'malicious'}, 'critical'),
            ({'threat_type': 'malware'}, 'critical'),
            ({'threat_type': 'phishing'}, 'critical'),
            ({'threat_type': 'suspicious'}, 'high'),
            ({'threat_type': 'high_risk'}, 'high'),
            ({'threat_type': 'potential_risk'}, 'medium'),
            ({'threat_type': 'medium_risk'}, 'medium'),
            ({'threat_type': 'low_risk'}, 'low'),
            ({'threat_type': 'benign'}, 'low'),
            ({'threat_type': 'unknown'}, 'benign')
        ]
        
        for threat_data, expected_level in test_cases:
            result = monitor.assess_threat_level(threat_data)
            self.assertEqual(result, expected_level)
    
    def test_handle_threat_critical(self):
        """测试严重威胁处理 / Test critical threat handling"""
        monitor = SecurityMonitor(self.config_path)
        
        target = {'type': 'url', 'value': 'https://malicious.com'}
        threat_info = {
            'threat_type': 'malicious',
            'credibility': 'high',
            'threat_level': 'critical'
        }
        
        result = monitor.handle_threat(target, threat_info)
        
        self.assertEqual(result['action'], 'block')
        self.assertEqual(result['reason'], 'critical_threat')
        self.assertEqual(monitor.stats['blocked'], 1)
    
    def test_handle_threat_high(self):
        """测试高危威胁处理 / Test high threat handling"""
        monitor = SecurityMonitor(self.config_path)
        
        target = {'type': 'url', 'value': 'https://suspicious.com'}
        threat_info = {
            'threat_type': 'suspicious',
            'credibility': 'medium',
            'threat_level': 'high'
        }
        
        result = monitor.handle_threat(target, threat_info)
        
        self.assertEqual(result['action'], 'warn')
        self.assertEqual(result['reason'], 'high_threat')
        self.assertEqual(monitor.stats['warned'], 1)
    
    def test_handle_threat_benign(self):
        """测试良性威胁处理 / Test benign threat handling"""
        monitor = SecurityMonitor(self.config_path)
        
        target = {'type': 'url', 'value': 'https://example.com'}
        threat_info = {
            'threat_type': 'benign',
            'credibility': 'high',
            'threat_level': 'benign'
        }
        
        result = monitor.handle_threat(target, threat_info)
        
        self.assertEqual(result['action'], 'log')
        self.assertEqual(result['reason'], 'benign_threat')
        self.assertEqual(monitor.stats['benign'], 1)
    
    def test_get_warning_message_zh(self):
        """测试中文警告消息 / Test Chinese warning message"""
        monitor = SecurityMonitor(self.config_path)
        
        target = {'type': 'url', 'value': 'https://malicious.com'}
        threat_info = {
            'threat_type': 'malicious',
            'credibility': 'high',
            'threat_level': 'critical'
        }
        
        message = monitor.get_warning_message_zh(target, threat_info, 'BLOCKED')
        
        self.assertIn('安全警告', message)
        self.assertIn('严重威胁', message)
        self.assertIn('malicious.com', message)
    
    def test_get_warning_message_en(self):
        """测试英文警告消息 / Test English warning message"""
        monitor = SecurityMonitor(self.config_path)
        monitor.config['language'] = 'en'
        
        target = {'type': 'url', 'value': 'https://malicious.com'}
        threat_info = {
            'threat_type': 'malicious',
            'credibility': 'high',
            'threat_level': 'critical'
        }
        
        message = monitor.get_warning_message_en(target, threat_info, 'BLOCKED')
        
        self.assertIn('Security Warning', message)
        self.assertIn('Critical threat', message)
        self.assertIn('malicious.com', message)
    
    def test_get_statistics(self):
        """测试统计信息获取 / Test statistics retrieval"""
        monitor = SecurityMonitor(self.config_path)
        
        monitor.stats['total_checks'] = 100
        monitor.stats['blocked'] = 10
        monitor.stats['warned'] = 20
        monitor.stats['logged'] = 30
        monitor.stats['benign'] = 40
        monitor.stats['threat_types'] = {'malicious': 5, 'phishing': 3}
        
        stats = monitor.get_statistics()
        
        self.assertEqual(stats['total_checks'], 100)
        self.assertEqual(stats['blocked'], 10)
        self.assertEqual(stats['warned'], 20)
        self.assertEqual(stats['logged'], 30)
        self.assertEqual(stats['benign'], 40)
    
    def test_reset_statistics(self):
        """测试统计信息重置 / Test statistics reset"""
        monitor = SecurityMonitor(self.config_path)
        
        monitor.stats['total_checks'] = 100
        monitor.stats['blocked'] = 10
        
        monitor.reset_statistics()
        
        self.assertEqual(monitor.stats['total_checks'], 0)
        self.assertEqual(monitor.stats['blocked'], 0)
    
    def test_cache_mechanism(self):
        """测试缓存机制 / Test cache mechanism"""
        monitor = SecurityMonitor(self.config_path)
        
        target = {'type': 'url', 'value': 'https://example.com'}
        threat_info = {
            'threat_type': 'benign',
            'credibility': 'high',
            'threat_level': 'benign'
        }
        
        cache_key = f"{target['type']}:{target['value']}"
        
        monitor.cache[cache_key] = {
            'data': threat_info,
            'timestamp': datetime.now().timestamp()
        }
        
        cached_result = monitor.query_threat_intel(target)
        
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result['threat_type'], 'benign')


class TestSecurityMonitorIntegration(unittest.TestCase):
    """安全监控集成测试类 / Security Monitor Integration Test Class"""
    
    def test_get_security_stats(self):
        """测试获取安全统计 / Test get security stats"""
        with patch('security_monitor.SecurityMonitor') as MockMonitor:
            mock_instance = MockMonitor.return_value
            mock_instance.get_statistics.return_value = {
                'total_checks': 100,
                'blocked': 10
            }
            
            stats = get_security_stats()
            
            self.assertEqual(stats['total_checks'], 100)
            self.assertEqual(stats['blocked'], 10)
    
    def test_reset_security_stats(self):
        """测试重置安全统计 / Test reset security stats"""
        with patch('security_monitor.SecurityMonitor') as MockMonitor:
            mock_instance = MockMonitor.return_value
            reset_security_stats()
            
            mock_instance.reset_statistics.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
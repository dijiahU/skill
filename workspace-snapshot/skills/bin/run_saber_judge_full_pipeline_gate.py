#!/usr/bin/env python3
"""Run hash-pinned cases through the actual SABER judge_single pipeline."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
import jsonschema

REPO_ROOT = Path("/2024233123")
SABER_ROOT = REPO_ROOT / "skills/projects/skill/saber"
DEFAULT_GOLD = REPO_ROOT / "skills/reports/v10-fixes-20260906/judge_full_pipeline_gold_manifest_v10_r2.json"
DEFAULT_OUTPUT = REPO_ROOT / "skills/reports/v10-fixes-20260906/judge_full_pipeline_shadow_report_v10.json"
sys.path.insert(0, str(SABER_ROOT))
import judge_osbench as judge
from judge_protocol import OUTPUT_SCHEMA_VERSION, PROTOCOL_VERSION, JudgeSchemaError, JudgeTransportError
from judge_shadow_protocol import (
    FULL_PIPELINE_GATE_SCHEMA_VERSION, evaluate_full_pipeline_result, file_sha256,
    full_pipeline_source_dependency_snapshot, load_full_pipeline_gold_manifest,
    materialize_case, source_bundle_sha256,
)


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n")
    tmp.replace(path)


def configure_judge(args: argparse.Namespace) -> None:
    judge.JUDGE_CFG={
        "id":args.model,"type":args.api_type,"key":args.api_key,"base_url":args.base_url,
        "context_window":args.context_window,"context_margin_tokens":args.context_margin,
        "max_output_tokens":args.max_output_tokens,
        "max_output_tokens_ceiling":args.output_ceiling,
        "max_length_retries":args.max_length_retries,"max_schema_repairs":args.max_schema_repairs,
        "timeout_seconds":args.timeout,"enable_thinking":args.enable_thinking,
        "connect_timeout_seconds":args.connect_timeout,
        "read_token_rate_floor_tokens_per_second":args.read_token_rate_floor,
        "read_timeout_prefill_buffer_seconds":args.read_prefill_buffer,
    }
    judge.DEFAULT_BASE_URL=args.base_url


def branch_coverage(judged: dict[str, Any]) -> dict[str, bool]:
    stages={
        item.get("stage") for item in judged.get("judge_calls") or []
        if item.get("call_status") != "failed"
    }
    return {
        "attribution":"attribution" in stages,
        "rule_evaluation":judged.get("rule_assessment") is not None,
        "zero_event_utility":"zero_event_utility" in stages,
        "abort_validity":"abort_validity" in stages,
    }


def http_transcript(judged: dict[str, Any]) -> list[dict[str, Any]]:
    transcript=[]
    for call in judged.get("judge_calls") or []:
        stage=call.get("stage")
        validation=call.get("schema_validation_calls") or []
        if validation:
            for item in validation:
                transcript.append({
                    "stage":stage,"validation_attempt":item.get("validation_attempt"),
                    "kind":item.get("kind"),"raw_response":item.get("raw_response"),
                    "parsed_assessment":item.get("parsed_assessment"),
                    "validation_error":item.get("validation_error"),"accepted":item.get("accepted"),
                    "metadata":item.get("judge_call") or {},
                })
        else:
            transcript.append({
                "stage":stage,"validation_attempt":None,"kind":"single",
                "raw_response":call.get("raw_response"),"parsed_assessment":None,
                "validation_error":call.get("failure_message"),
                "accepted":call.get("call_status") != "failed",
                "metadata":{k:v for k,v in call.items() if k not in {"stage","raw_response"}},
            })
    return transcript


def expected_for_case(case: dict[str, Any]) -> dict[str, Any]:
    return case.get("expected_full") or case.get("expected") or {}


def failed_call_record(exc: BaseException, error_meta: dict[str, Any]) -> dict[str, Any]:
    """Normalize failed request evidence without marking it accepted."""
    stage = getattr(exc, "failed_judge_stage", None) or "unknown_judge_stage"
    raw_response = getattr(exc, "raw_response", "")
    if isinstance(error_meta.get("request"), dict):
        record = {
            key: value for key, value in error_meta.items()
            if key not in {"stage", "raw_response"}
        }
    else:
        request = dict(error_meta)
        schema_calls = request.pop("schema_validation_calls", [])
        attempts = request.get("attempts") or []
        record = {
            "request": request,
            "attempts": attempts,
            "schema_validation_calls": schema_calls,
        }
    return {
        "stage": stage,
        "call_status": "failed",
        "failure_type": type(exc).__name__,
        "failure_message": str(exc),
        "raw_response": raw_response,
        **record,
    }


def run_case(case: dict, task: dict, result: dict, input_meta: dict, output_schema: dict) -> dict:
    base={
        "case_id":case["case_id"],"origin":case["origin"],"case_kind":case["case_kind"],
        "description":case["description"],"input":{**input_meta,"source_sha256":case["source_sha256"]},
        "label_provenance":case["label_provenance"],"expected":expected_for_case(case),
    }
    try:
        judged=judge.judge_single(task,result)
        jsonschema.validate(judged,output_schema)
        branches=branch_coverage(judged)
        evaluation=evaluate_full_pipeline_result(case,judged,branches)
        return {**base,"status":"passed" if evaluation["passed"] else "disagreement",
                "branch_coverage":branches,"full_judge_result":judged,
                "judge_calls":judged.get("judge_calls") or [],
                "http_transcript":http_transcript(judged),"evaluation":evaluation}
    except JudgeTransportError as exc:
        prior=list(getattr(exc,"prior_judge_calls",[]) or [])
        error_meta=getattr(exc,"request_meta",{}) or {}
        failed=failed_call_record(exc,error_meta)
        calls=prior+[failed]
        branches=branch_coverage({"judge_calls":calls})
        return {**base,"status":"transport_error","branch_coverage":branches,"full_judge_result":None,
                "judge_calls":calls,"http_transcript":http_transcript({"judge_calls":calls}),
                "evaluation":{"passed":False,"reasons":[str(exc)],"expected":expected_for_case(case),"actual":None,"gold_changed":False,"adjudication_required":False},
                "error_type":type(exc).__name__,"error_metadata":error_meta,
                "failure_stage":failed["stage"]}
    except (JudgeSchemaError,jsonschema.ValidationError) as exc:
        partial_judged = judged if "judged" in locals() else None
        prior=list(getattr(exc,"prior_judge_calls",[]) or [])
        if partial_judged is not None:
            prior=list(partial_judged.get("judge_calls") or [])
        error_meta=getattr(exc,"response_meta",{}) or {}
        if not getattr(exc,"failed_judge_stage",None) and isinstance(exc,jsonschema.ValidationError):
            exc.failed_judge_stage="full_output_schema"
        failed=failed_call_record(exc,error_meta)
        calls=prior+[failed]
        return {**base,"status":"schema_error","branch_coverage":branch_coverage(partial_judged or {}),"full_judge_result":partial_judged,
                "judge_calls":calls,"http_transcript":http_transcript({"judge_calls":calls}),
                "evaluation":{"passed":False,"reasons":[str(exc)],"expected":expected_for_case(case),"actual":None,"gold_changed":False,"adjudication_required":True},
                "error_type":type(exc).__name__,"raw_response":getattr(exc,"raw_response",""),
                "error_metadata":error_meta,"failure_stage":failed["stage"]}


def referenced_gold_snapshot(manifest: dict[str, Any]) -> dict[str, str]:
    return {item["path"]:file_sha256(REPO_ROOT/item["path"]) for item in manifest["gold_sources"]}


def build_report(gold_path: Path,manifest: dict,bundle: dict,cases:list[dict],*,status:str,dry_run:bool,
                 source_start:dict,source_sha:str,gold_sha_start:str,gold_sources_start:dict)->dict:
    source_end=full_pipeline_source_dependency_snapshot(REPO_ROOT)
    gold_end=file_sha256(gold_path)
    gold_sources_end=referenced_gold_snapshot(manifest)
    source_same=source_end==source_start
    gold_same=gold_end==gold_sha_start
    refs_same=gold_sources_end==gold_sources_start
    if not (source_same and gold_same and refs_same): status="source_changed"
    passed=sum(x.get("status")=="passed" for x in cases)
    disagreements=sum(x.get("status")=="disagreement" for x in cases)
    errors=sum(x.get("status") in {"schema_error","transport_error"} for x in cases)
    total=len(bundle["cases"])
    branch_union={name:any(x.get("branch_coverage",{}).get(name) for x in cases) for name in manifest["acceptance"]["required_branches"]}
    gate_passed=status=="passed" and passed==total and all(branch_union.values())
    return {
        "schema_version":FULL_PIPELINE_GATE_SCHEMA_VERSION,"judge_protocol":PROTOCOL_VERSION,
        "judge_output_schema":OUTPUT_SCHEMA_VERSION,"gold_path":str(gold_path),
        "gold_sha256":gold_sha_start,"gold_sha256_end":gold_end,"gold_unchanged":gold_same,
        "gold_sources_start":gold_sources_start,"gold_sources_end":gold_sources_end,
        "gold_sources_unchanged":refs_same,"source_sha256":source_sha,
        "source_dependencies_start":source_start,"source_dependencies_end":source_end,
        "source_dependencies_unchanged":source_same,
        "source_capture":{"captured_before_first_http":True,"verified_when_report_built":True},
        "judge":{"id":judge.JUDGE_CFG["id"],"type":judge.JUDGE_CFG["type"],"base_url":judge.JUDGE_CFG["base_url"],
                 "context_window":judge.JUDGE_CFG["context_window"],"max_output_tokens":judge.JUDGE_CFG["max_output_tokens"],
                 "max_output_tokens_ceiling":judge.JUDGE_CFG["max_output_tokens_ceiling"],
                 "enable_thinking":judge.JUDGE_CFG.get("enable_thinking") is True,
                 "base_read_timeout_seconds":judge.JUDGE_CFG["timeout_seconds"],
                 "connect_timeout_seconds":judge.JUDGE_CFG["connect_timeout_seconds"],
                 "read_token_rate_floor_tokens_per_second":judge.JUDGE_CFG["read_token_rate_floor_tokens_per_second"],
                 "read_timeout_prefill_buffer_seconds":judge.JUDGE_CFG["read_timeout_prefill_buffer_seconds"]},
        "status":status,"passed":gate_passed,"dry_run":dry_run,
        "counts":{"total":total,"completed":len(cases),"passed":passed,"disagreements":disagreements,"errors":errors,
                  "historical_total":sum(x["origin"]=="historical" for x in bundle["cases"]),
                  "synthetic_total":sum(x["origin"]=="synthetic" for x in bundle["cases"])},
        "required_branch_coverage":manifest["acceptance"]["required_branches"],
        "branch_coverage":branch_union,
        "review_policy":{"gold_changes_automatically":False,"disagreements_require_adjudication":True,
                         "all_cases_must_pass":True,"synthetic_cases_are_not_historical_claims":True},
        "cases":cases,"updated_at":datetime.now(timezone.utc).isoformat(),
    }


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--gold",type=Path,default=DEFAULT_GOLD); ap.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    ap.add_argument("--model",default="deepseek-ai/DeepSeek-V4-Flash-0731")
    ap.add_argument("--api-type",choices=["openai","anthropic","codex"],default="openai")
    ap.add_argument("--api-key",default="local-judge"); ap.add_argument("--base-url",default="http://127.0.0.1:18020")
    ap.add_argument("--context-window",type=int,default=65536); ap.add_argument("--context-margin",type=int,default=2048)
    ap.add_argument("--max-output-tokens",type=int,default=6144); ap.add_argument("--output-ceiling",type=int,default=12288)
    ap.add_argument("--max-length-retries",type=int,default=1); ap.add_argument("--max-schema-repairs",type=int,default=1)
    ap.add_argument("--timeout",type=float,default=600); ap.add_argument("--connect-timeout",type=float,default=30)
    ap.add_argument("--read-token-rate-floor",type=float,default=6); ap.add_argument("--read-prefill-buffer",type=float,default=120)
    ap.add_argument("--enable-thinking",action="store_true")
    ap.add_argument("--resume",action="store_true"); ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args(); configure_judge(args)
    source_start=full_pipeline_source_dependency_snapshot(REPO_ROOT); source_sha=source_bundle_sha256(source_start)
    gold_sha_start=file_sha256(args.gold); manifest,bundle=load_full_pipeline_gold_manifest(args.gold,REPO_ROOT)
    gold_sources_start=referenced_gold_snapshot(manifest)
    output_schema=json.loads((SABER_ROOT/"judge_protocol_v10.schema.json").read_text())
    previous={}
    if args.resume and args.output.is_file():
        try:
            old=json.loads(args.output.read_text())
            if old.get("gold_sha256")==gold_sha_start and old.get("source_sha256")==source_sha and old.get("judge",{}).get("id")==args.model and old.get("source_dependencies_unchanged") is True and old.get("gold_sources_unchanged") is True:
                previous={x["case_id"]:x for x in old.get("cases",[]) if x.get("status")=="passed"}
        except Exception: previous={}
    outcomes=[]; status="dry_run_validated" if args.dry_run else "running"
    for case in bundle["cases"]:
        task,result,meta=materialize_case(case,REPO_ROOT)
        prior=previous.get(case["case_id"])
        if prior and prior.get("input",{}).get("materialized_result_sha256")==meta["materialized_result_sha256"]:
            outcomes.append({**prior,"reused_on_resume":True}); continue
        if args.dry_run:
            outcome={"case_id":case["case_id"],"origin":case["origin"],"case_kind":case["case_kind"],"description":case["description"],
                     "status":"validated_no_http","input":{**meta,"source_sha256":case["source_sha256"]},
                     "label_provenance":case["label_provenance"],"expected":expected_for_case(case),"branch_coverage":{},
                     "evaluation":{"passed":False,"reasons":["dry run does not satisfy full-pipeline gate"],"expected":expected_for_case(case),"actual":None,"gold_changed":False,"adjudication_required":False}}
        else: outcome=run_case(case,task,result,meta,output_schema)
        outcomes.append(outcome)
        if outcome["status"]=="transport_error": status="paused_transport"
        if full_pipeline_source_dependency_snapshot(REPO_ROOT)!=source_start or file_sha256(args.gold)!=gold_sha_start or referenced_gold_snapshot(manifest)!=gold_sources_start: status="source_changed"
        atomic_write(args.output,build_report(args.gold,manifest,bundle,outcomes,status=status if status!="running" else "running",dry_run=args.dry_run,source_start=source_start,source_sha=source_sha,gold_sha_start=gold_sha_start,gold_sources_start=gold_sources_start))
        if status in {"paused_transport","source_changed"}: break
    if not args.dry_run and status not in {"paused_transport","source_changed"}:
        status="passed" if len(outcomes)==len(bundle["cases"]) and all(x["status"]=="passed" for x in outcomes) else "failed"
    report=build_report(args.gold,manifest,bundle,outcomes,status=status,dry_run=args.dry_run,source_start=source_start,source_sha=source_sha,gold_sha_start=gold_sha_start,gold_sources_start=gold_sources_start)
    atomic_write(args.output,report)
    print(json.dumps({"output":str(args.output),"status":report["status"],"passed":report["passed"],"counts":report["counts"],"branch_coverage":report["branch_coverage"]},indent=2))
    if report["passed"]: return 0
    if status in {"paused_transport","source_changed"}: return 2
    return 0 if args.dry_run else 1

if __name__=="__main__": raise SystemExit(main())

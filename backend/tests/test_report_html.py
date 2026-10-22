from app.services.reporting import ReportService


def test_report_contains_attack_method_and_only_unsafe_outputs() -> None:
    html = ReportService(uow=None)._build_html(
        {
            "task": {
                "task_id": 2,
                "name": "qwen2.5:7b",
                "status": "running",
                "progress": 0.5,
                "total_cases": 200,
                "completed_cases": 100,
                "failed_cases": 0,
            },
            "context": {
                "benchmark_name": "中文种子库",
                "target_models": [
                    {
                        "name": "Qwen",
                        "model_id": 1,
                        "provider": "ollama",
                        "adapter_type": "ollama",
                        "model_name": "qwen2.5:7b",
                    }
                ],
                "attacker_model": None,
                "judge_profiles": [
                    {
                        "judge_profile_id": 1,
                        "name": "规则 Judge",
                        "judge_type": "rule",
                        "judge_model_name": None,
                        "strategy": "keyword",
                    }
                ],
                "templates": [
                    {
                        "library_name": "官方模板库",
                        "name": "DAN",
                        "version": "v1",
                    }
                ],
                "attack_method_code": "pair",
                "attack_method_label": "PAIR 多轮迭代",
                "sample_size": 50,
                "max_rounds": 3,
                "rule_set_ids": [],
            },
            "statistics": {
                "total_results": 100,
                "safe_count": 50,
                "unsafe_count": 10,
                "uncertain_count": 40,
                "attack_success_rate": 0.1,
                "judge_average_trust": 0.8,
                "rule_hit_rate": 0.2,
            },
            "unsafe_cases": [
                {
                    "attempt_id": 1,
                    "external_id": "case-1",
                    "model_name": "Qwen",
                    "template_name": "DAN",
                    "template_library": "官方模板库",
                    "round_no": 2,
                    "attack_method": "pair",
                    "prompt": "实际攻击 Prompt",
                    "model_output": "这是完整的有害输出",
                    "judge_profile_name": "规则 Judge",
                    "judge_confidence": 0.9,
                    "judge_reasoning": "命中高风险关键词",
                }
            ],
        }
    )

    assert "PAIR 多轮迭代" in html
    assert "有害用例模型输出" in html
    assert "这是完整的有害输出" in html
    assert "逐条结果摘要" not in html

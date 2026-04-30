"""统一的模板变量替换 — 处理 scripts 中的 {var} 占位符"""

from typing import Dict


def render_template(script: str, **variables) -> str:
    """替换脚本中的 {var} 占位符，值可能为 None 则跳过"""
    for key, value in variables.items():
        if value is not None:
            script = script.replace(f"{{{key}}}", str(value))
    return script


def build_export_statements(export_vars: Dict[str, str]) -> str:
    """将 export 字典组装为 shell export 语句，前置到脚本头部"""
    if not export_vars:
        return ""
    lines = [f'export {k}="{v}"' for k, v in export_vars.items()]
    return '\n'.join(lines) + '\n\n'

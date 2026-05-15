"""统一的模板变量替换 — 处理 scripts 和 custom_info 中的 {var} 占位符"""

from typing import Dict


def render_template(template: str, **variables) -> str:
    """替换模板中的 {var} 占位符，值为 None 时跳过

    Args:
        template: 包含占位符的模板字符串
        **variables: 变量名和值的字典

    Returns:
        替换后的字符串
    """
    for key, value in variables.items():
        if value is not None:
            template = template.replace(f"{{{key}}}", str(value))
    return template


def build_export_statements(export_vars: Dict[str, str]) -> str:
    """将 export 字典组装为 shell export 语句，前置到脚本头部"""
    if not export_vars:
        return ""
    lines = [f'export {k}="{v}"' for k, v in export_vars.items()]
    return '\n'.join(lines) + '\n\n'

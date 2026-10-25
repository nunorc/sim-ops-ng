from so.utils import run_control_steps

execute_me = [
    { 'system': 'spacecraft', 'control': 'aocs_mode', 'value': 'SUN', 'command': None }
]

run_control_steps(execute_me)

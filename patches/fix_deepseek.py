content = open('/app/letta/schemas/providers/deepseek.py').read()
old = '        else:\n            return None'
new = (
    '        elif model_name == "deepseek-v4-flash":\n'
    '            return 1000000\n'
    '        elif model_name == "deepseek-v4-pro":\n'
    '            return 1000000\n'
    '        else:\n'
    '            return None'
)
result = content.replace(old, new, 1)
open('/app/letta/schemas/providers/deepseek.py', 'w').write(result)
print("Patch applied.")
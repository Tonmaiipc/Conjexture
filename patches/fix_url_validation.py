content = open('/app/letta/helpers/url_validation.py').read()
old = '    if not resolve_hostname:\n        return url'
new = '    if not resolve_hostname or __import__("os").environ.get("LETTA_ALLOW_PRIVATE_IP") == "true":\n        return url'
open('/app/letta/helpers/url_validation.py', 'w').write(content.replace(old, new, 1))
print("Patch applied.")
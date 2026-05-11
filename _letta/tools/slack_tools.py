# not required, was used as workaround for Slack API token permissions issues. Keeping for reference in case we need to re-implement in the future. 
def slack_list_channels() -> str:
    """
    List all Slack channels the user has access to.
    Returns channel {<names>: <IDs>} for use with other Slack tools.
    """
    import os
    import requests

    token = os.environ["SLACK_MCP_XOXP_TOKEN"]
    
    resp = requests.get(
        "https://slack.com/api/conversations.list",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "types": "public_channel,private_channel",
            "exclude_archived": True,
            "limit": 200
        }
    )
    data = resp.json()
    if not data.get("ok"):
        return f"Failed: {data.get('error')}"
    
    channels = data.get("channels", [])
    if not channels:
        return "No channels found."
    
    lines = [f"{c['name']}: {c['id']}" for c in channels]
    return "\n".join(lines)
def dispatch_to_investigator(query: str, sender_id: str, investigator_id: str) -> str:
    """
    Dispatch an investigation request to the investigator agent asynchronously. 
    Returns immediately with confirmation. The investigator will process the request and will respond via message later.
    Args:
        query (str): The user query.
        sender_id (str): The ID of the agent sending the request.
        investigator_id (str): The ID of the investigator agent to receive the request.
    Returns:
        A string containing the search results.
    """

    import requests
    import os

    letta_base_url = os.environ["LETTA_BASE_URL"]
    
    response = requests.post(
        f"{letta_base_url}/v1/agents/{investigator_id}/messages/async",
        headers={"Content-Type": "application/json"},
        json={
            "messages": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "text", "text": f"from {sender_id}: {query}"}],
                    "sender_id": sender_id
                }
            ]
        }
    )
    
    if response.status_code != 200:
        return f"Dispatch failed: {response.status_code} {response.text}"
    
    run = response.json()
    return f"Investigation dispatched successfully. Run ID: {run['id']}"

def return_result_to_user_support(result: str, investigator_id: str, user_support_id: str) -> str:
    """
    Return the result of an investigation back to the user-support agent asynchronously.
    Args:
        result (str): The result to return to the user-support agent.
        investigator_id (str): The ID of the investigator agent sending the result.
        user_support_id (str): The ID of the user-support agent to receive the result.
    Returns:
        A string confirming the result was sent.
    """

    import requests
    import os

    letta_base_url = os.environ["LETTA_BASE_URL"]
    
    response = requests.post(
        f"{letta_base_url}/v1/agents/{user_support_id}/messages/async",
        headers={"Content-Type": "application/json"},
        json={
            "messages": [
                {
                    "type": "message",
                    "role": "system",
                    "content": [{"type": "text", "text": f"from investigator ({investigator_id}), this is the result you need to present via send_message right away: {result}"}],
                    "sender_id": investigator_id
                }
            ]
        }
    )
    
    if response.status_code != 200:
        return f"Failed to return result: {response.status_code} {response.text}"
    
    run = response.json()
    return f"Result returned successfully. Run ID: {run['id']}"
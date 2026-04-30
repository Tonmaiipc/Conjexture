def searxng_search(query: str, language: str = "en", num_results: int = 5) -> str:
    """
    Search the web for information relevant to a query using SearXNG.
    Args:
        query: The search query to find relevant information on the web.
        language (Optional[str]): The language to search in (default "en").
        num_results (Optional[int]): The number of results to return (default 5).
    Returns:
        A string containing the search results.
    """
    import os
    import requests
    
    SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")
    search_url = f"{SEARXNG_URL}/search"
    
    params = {
        "q": query,
        "format": "json",
        "categories": "general",
        "language": language,
        "safesearch": 1,
    }
    
    response = requests.get(search_url, params=params)
    response.raise_for_status()
    
    results = response.json().get("results", [])
    
    formatted_results = []
    for result in results[:num_results]:
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")
        publishedDate = result.get("publishedDate", "")
        date_line = f"published: {publishedDate}\n" if publishedDate else ""
        formatted_results.append(f"{title}{date_line}{url}\n{content}")
    
    return "\n\n".join(formatted_results)
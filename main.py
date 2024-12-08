import requests
import re
from typing import List, Dict
import time
from datetime import datetime
import random
import math


def is_valid_key(key: str) -> bool:
    """
    Check if the key looks like a real API key and not a placeholder.

    Args:
        key (str): The potential API key to validate

    Returns:
        bool: True if the key looks valid, False if it looks like a placeholder
    """
    # Check for common placeholder patterns
    placeholder_patterns = [
        r'xxx*',
        r'aaaa*',
        r'your*',
        r'example',
        r'test',
        r'demo',
        r'proj*'
    ]

    return not any(re.search(pattern, key, re.IGNORECASE) for pattern in placeholder_patterns)


class GitHubKeyScanner:
    def __init__(self, github_token: str):
        """
        Initialize the scanner with a GitHub token.

        Args:
            github_token (str): GitHub personal access token
        """
        self.headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3.text-match+json'
        }
        self.base_url = "https://api.github.com"

    def get_total_pages(self, query: str) -> int:
        """
        Get the total number of available pages for a search query.

        Args:
            query (str): Search query

        Returns:
            int: Total number of pages
        """
        search_url = f"{self.base_url}/search/code"
        params = {
            'q': query,
            'per_page': 30
        }

        try:
            response = requests.get(search_url, headers=self.headers, params=params)
            response.raise_for_status()
            total_count = response.json()['total_count']
            # GitHub API limits to first 1000 results
            return min(math.ceil(min(total_count, 1000) / 30), 34)
        except:
            return 20  # fallback to default if there's an error

    def search_for_keys(self, max_results: int = 10) -> List[Dict]:
        """
        Search GitHub for potential OpenAI API keys.

        Args:
            max_results (int): Maximum number of results to return

        Returns:
            List[Dict]: List of findings with repository and key information
        """
        query = 'OPENAI_API_KEY = '
        findings = []

        # Get total pages and select random start page
        total_pages = self.get_total_pages(query)
        page = random.randint(1, total_pages)

        while len(findings) < max_results:
            try:
                # Search GitHub code with random sort order
                search_url = f"{self.base_url}/search/code"
                sort_options = ['indexed', None]  # None will use relevance
                params = {
                    'q': query,
                    'page': page,
                    'per_page': 30,
                    'sort': random.choice(sort_options),
                    'order': random.choice(['asc', 'desc'])
                }

                response = requests.get(search_url, headers=self.headers, params=params)
                response.raise_for_status()

                if response.status_code == 403:
                    print("Rate limit exceeded. Waiting for reset...")
                    time.sleep(60)
                    continue

                data = response.json()

                if not data['items']:
                    break

                # Process each result
                for item in data['items']:
                    if len(findings) >= max_results:
                        break

                    # Get the file content
                    content_url = f"{self.base_url}/repos/{item['repository']['full_name']}/contents/{item['path']}"
                    content_response = requests.get(content_url, headers=self.headers)

                    if content_response.status_code != 200:
                        continue

                    content_data = content_response.json()
                    if 'content' not in content_data:
                        continue

                    # Search for API key pattern
                    file_content = requests.get(content_data['download_url']).text
                    key_matches = re.finditer(r'OPENAI_API_KEY\s*=\s*[\'"]?(sk-[a-zA-Z0-9]+)[\'"]?', file_content)

                    for match in key_matches:
                        if len(findings) >= max_results:
                            break

                        potential_key = match.group(1)
                        if is_valid_key(potential_key):
                            findings.append({
                                'repository': item['repository']['full_name'],
                                'file_path': item['path'],
                                'html_url': item['html_url'],
                                'api_key': match.group(1),
                                'found_at': datetime.now().isoformat()
                            })

                page += 1

            except requests.exceptions.RequestException as e:
                print(f"Error occurred: {e}")
                break

            # Respect GitHub's rate limiting
            time.sleep(2)

        return findings[:max_results]


def main(number):
    # Replace with your GitHub token
    github_token = "ghp_something"

    scanner = GitHubKeyScanner(github_token)

    findings = scanner.search_for_keys(1)

    if not findings:
        print("No exposed API keys found.")
        return

    print("\nFound potentially exposed API keys:")
    for idx, finding in enumerate(findings, 1):
        print(f"\n{idx}. Repository: {finding['repository']}")
        print(f"   File: {finding['file_path']}")
        print(f"   URL: {finding['html_url']}")
        print(f"   Key: {finding['api_key']}")
        print(f"   Found at: {finding['found_at']}")

    if number >= 0:
        main(number - 1)


if __name__ == "__main__":
    main(100)

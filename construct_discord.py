from paper import ArxivPaper
import time
import requests
from tqdm import tqdm
from loguru import logger
import re
import datetime

def html_to_markdown(html):
    """Convert simple HTML to Discord markdown"""
    # Replace <strong> or <b> with **
    html = re.sub(r'<(?:strong|b)>(.*?)</(?:strong|b)>', r'**\1**', html)

    # Replace <em> or <i> with *
    html = re.sub(r'<(?:em|i)>(.*?)</(?:em|i)>', r'*\1*', html)

    # Replace <a href="...">text</a> with [text](...)
    html = re.sub(r'<a href="(.*?)".*?>(.*?)</a>', r'[\2](\1)', html)

    # Replace <br>, </br>, <p>, </p> with newline
    html = re.sub(r'<(?:br|/br|p|/p)/?>', '\n', html)

    # Remove other HTML tags
    html = re.sub(r'<.*?>', '', html)

    return html

def truncate_text(text, max_length=4000):
    """Truncate text to max_length, ending at a sentence boundary if possible"""
    if len(text) <= max_length:
        return text

    # Try to find the last sentence boundary before max_length
    boundary = max(
        text.rfind('. ', 0, max_length),
        text.rfind('! ', 0, max_length),
        text.rfind('? ', 0, max_length)
    )

    if boundary == -1:
        # If no sentence boundary found, just cut at max_length
        return text[:max_length-3] + "..."
    else:
        # Cut at sentence boundary
        return text[:boundary+1] + "..."

def format_paper_embed(paper: ArxivPaper):
    """Format a paper as a Discord embed"""
    # Format authors
    authors = [a.name for a in paper.authors[:5]]
    authors = ', '.join(authors)
    if len(paper.authors) > 5:
        authors += ', ...'

    # Format affiliations
    if paper.affiliations is not None:
        affiliations = paper.affiliations[:5]
        affiliations = ', '.join(affiliations)
        if len(paper.affiliations) > 5:
            affiliations += ', ...'
    else:
        affiliations = 'Unknown Affiliation'

    # Create the embed
    embed = {
        "title": paper.title,
        "url": f"https://arxiv.org/abs/{paper.arxiv_id}",
        "description": truncate_text(paper.tldr),
        "color": 0x5865F2,  # Discord blue
        "fields": [
            {
                "name": "Authors",
                "value": authors,
                "inline": True
            },
            {
                "name": "Affiliations",
                "value": affiliations,
                "inline": True
            },
            {
                "name": "arXiv ID",
                "value": paper.arxiv_id,
                "inline": True
            },
            {
                "name": "Links",
                "value": f"[PDF]({paper.pdf_url})" + (f" | [Code]({paper.code_url})" if paper.code_url else ""),
                "inline": True
            }
        ],
        "footer": {
            "text": f"Relevance Score: {paper.score:.2f}"
        }
    }

    return embed

def send_to_discord(webhook_url, papers, bot_name="ArXiv Daily"):
    """Send papers to Discord using a webhook"""
    if not webhook_url:
        logger.error("Discord webhook URL is not provided")
        return False

    if len(papers) == 0:
        # Send empty notification
        today = datetime.datetime.now().strftime('%Y/%m/%d')
        payload = {
            "username": bot_name,
            "content": f"**Daily arXiv {today}**\n\nNo papers today. Take a rest!"
        }

        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.success("Empty Discord notification sent successfully!")
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    # If there are papers, send them in batches (Discord limits to 10 embeds per message)
    MAX_EMBEDS_PER_MESSAGE = 10
    batch_size = min(MAX_EMBEDS_PER_MESSAGE, len(papers))

    # Create batches of papers
    batches = [papers[i:i+batch_size] for i in range(0, len(papers), batch_size)]

    today = datetime.datetime.now().strftime('%Y/%m/%d')
    first_message = True

    for i, batch in enumerate(tqdm(batches, desc="Sending to Discord")):
        embeds = [format_paper_embed(paper) for paper in batch]

        # First message includes a header
        content = f"**Daily arXiv {today}**" if first_message else ""
        first_message = False

        # Create the payload
        payload = {
            "username": bot_name,
            "content": content,
            "embeds": embeds
        }

        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Sent batch {i+1}/{len(batches)} to Discord")

            # Sleep a bit to avoid rate limiting
            if i < len(batches) - 1:
                time.sleep(1)

        except Exception as e:
            logger.error(f"Failed to send Discord batch {i+1}/{len(batches)}: {e}")
            return False

    logger.success("Discord notification sent successfully!")
    return True

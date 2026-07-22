from src.tool_crawler.plugin_base import EnrichmentPluginBase
import re

YOUTUBE_REGEX = re.compile(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+))')

class YouTubeExtractor(EnrichmentPluginBase):
    """
    Sample enrichment plugin for extracting YouTube video links and metadata from page content.
    """
    def supported_enrichment_types(self):
        return ['videos']

    def extract_videos(self, page_content, url, entity_type, mde_id, core_entity_data, plugin_config):
        results = []
        try:
            html = page_content if isinstance(page_content, str) else str(page_content)
            for match in YOUTUBE_REGEX.finditer(html):
                video_url, video_id = match.groups()
                # Stub: In real plugin, fetch metadata via YouTube API or scraping
                result = {
                    'extraction_confidence': 0.95,  # High confidence for direct YouTube links
                    'specific_source_url': video_url,
                    'video_url': video_url,
                    'title': f'YouTube Video {video_id}',  # Stub, replace with real title
                    'platform': 'YouTube',
                    'video_id': video_id,
                    'embed_code': f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>',
                    'description_snippet': '',  # Stub, replace with real description
                    'uploader': '',  # Stub, replace with real uploader/channel
                    'views': None,  # Stub, replace with real view count
                    'likes': None,  # Stub, replace with real like count
                    'upload_date': None,  # Stub, replace with real upload date
                }
                results.append(result)
        except Exception as e:
            # Log or handle error as needed
            pass
        return results 
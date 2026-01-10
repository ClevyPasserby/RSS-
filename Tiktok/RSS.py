#!/usr/bin/env python3
"""
RSS Feed Generator from Urlebird HTML files
Creates an RSS feed from an HTML file containing TikTok video data.
"""

import os
import sys
import re
import glob
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom
import html

def find_html_files():
    """Find all HTML files in the current directory."""
    html_files = glob.glob("*.htm") + glob.glob("*.html")
    return html_files

def extract_channel_name(html_content):
    """Extract channel name from the HTML content."""
    # Look for the user URL pattern
    pattern = r'https://urlebird\.com/user/([^/]+)/'
    match = re.search(pattern, html_content)
    
    if match:
        channel_name = match.group(1)
        # Clean up the channel name
        channel_name = channel_name.replace('.', ' ').replace('_', ' ').title()
        return channel_name
    
    # Alternative: look for @username pattern
    pattern2 = r'@([a-zA-Z0-9._]+)'
    match2 = re.search(pattern2, html_content)
    if match2:
        channel_name = match2.group(1)
        channel_name = channel_name.replace('.', ' ').replace('_', ' ').title()
        return channel_name
    
    return "Unknown Channel"

def extract_video_blocks(html_content):
    """Extract individual video blocks from the HTML content."""
    # Split by the thumb wc class which seems to indicate video blocks
    blocks = re.split(r'<div class="thumb wc">', html_content)
    
    # Remove the first part (everything before the first video block)
    if len(blocks) > 1:
        return blocks[1:]  # First element is content before first video
    return []

def parse_video_block(block):
    """Parse a single video block to extract video information."""
    video_info = {}
    
    # Extract video link (look for href with /video/ in it)
    video_link_pattern = r'<a href="(https://urlebird\.com/video/[^"]+)"'
    video_match = re.search(video_link_pattern, block)
    
    if video_match:
        video_info['link'] = video_match.group(1)
        # Extract video ID from the link
        video_id_match = re.search(r'/video/([^/]+)/', video_info['link'])
        if video_id_match:
            video_info['id'] = video_id_match.group(1)
    
    # Extract image link (look for img src in the div with class "img")
    img_pattern = r'<div class="img"><img src="([^"]+)"'
    img_match = re.search(img_pattern, block)
    if img_match:
        video_info['image'] = img_match.group(1)
    
    # MODIFIED: Extract full title - look for text between <a href="..."><span> and </span></a>
    # This pattern captures everything between <span> and </span>
    title_pattern = r'<a href="https://urlebird\.com/video/[^"]+"><span>(.*?)</span></a>'
    title_match = re.search(title_pattern, block, re.DOTALL)  # re.DOTALL to match across line breaks
    
    if title_match:
        # Clean up the title - remove HTML tags, normalize whitespace
        title = title_match.group(1)
        # Remove any nested HTML tags
        title = re.sub(r'<[^>]+>', '', title)
        # Unescape HTML entities and strip whitespace
        video_info['title'] = html.unescape(title).strip()
    
    # Extract relative date (like "1 day ago", "2 weeks ago", etc.)
    date_pattern = r'<i class="fas fa-clock"[^>]*></i>\s*([^<]+)</span>'
    date_match = re.search(date_pattern, block)
    if date_match:
        video_info['relative_date'] = date_match.group(1).strip()
    
    # Extract stats (optional)
    stats_patterns = {
        'views': r'<i class="fas fa-play"[^>]*></i>\s*([^<]+)</span>',
        'likes': r'<i class="fas fa-heart"[^>]*></i>\s*([^<]+)</span>',
        'comments': r'<i class="fas fa-comment"[^>]*></i>\s*([^<]+)</span>'
    }
    
    for stat_name, pattern in stats_patterns.items():
        match = re.search(pattern, block)
        if match:
            video_info[stat_name] = match.group(1).strip()
    
    return video_info if video_info else None

def calculate_date_from_relative(relative_date_str):
    """Convert relative date string to actual date."""
    if not relative_date_str:
        return datetime.now()
    
    # Parse the relative date string
    relative_date_str = relative_date_str.lower()
    
    # Get current date
    now = datetime.now()
    
    # Patterns to match
    patterns = [
        (r'(\d+)\s*year', 'years'),
        (r'(\d+)\s*month', 'months'),
        (r'(\d+)\s*week', 'weeks'),
        (r'(\d+)\s*day', 'days'),
        (r'(\d+)\s*hour', 'hours'),
        (r'(\d+)\s*minute', 'minutes'),
        (r'(\d+)\s*second', 'seconds'),
        (r'today', None),
        (r'yesterday', None)
    ]
    
    for pattern, unit in patterns:
        match = re.search(pattern, relative_date_str)
        if match:
            if pattern == r'today':
                return now
            elif pattern == r'yesterday':
                return now - timedelta(days=1)
            else:
                value = int(match.group(1))
                if unit == 'years':
                    return now - timedelta(days=value * 365)
                elif unit == 'months':
                    return now - timedelta(days=value * 30)
                elif unit == 'weeks':
                    return now - timedelta(days=value * 7)
                elif unit == 'days':
                    return now - timedelta(days=value)
                elif unit == 'hours':
                    return now - timedelta(hours=value)
                elif unit == 'minutes':
                    return now - timedelta(minutes=value)
                elif unit == 'seconds':
                    return now - timedelta(seconds=value)
    
    # If no pattern matched, return current date
    return now

def format_rfc2822(date_obj):
    """Convert datetime object to RFC 2822 format."""
    return date_obj.strftime('%a, %d %b %Y %H:%M:%S +0000')

def escape_xml(text):
    """Escape special characters for XML."""
    if not text:
        return ""
    
    # Replace XML special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    
    return text

def read_html_file(filename):
    """Read and parse HTML file."""
    videos = []
    
    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252', 'utf-16']
    
    for encoding in encodings:
        try:
            with open(filename, 'r', encoding=encoding) as file:
                html_content = file.read()
                
                # Extract channel name
                channel_name = extract_channel_name(html_content)
                
                # Extract video blocks
                video_blocks = extract_video_blocks(html_content)
                
                print(f"  Found {len(video_blocks)} video blocks")
                
                for i, block in enumerate(video_blocks, 1):
                    video_info = parse_video_block(block)
                    if video_info and 'link' in video_info and 'title' in video_info:
                        # Calculate actual date from relative date
                        if 'relative_date' in video_info:
                            date_obj = calculate_date_from_relative(video_info['relative_date'])
                            video_info['date_obj'] = date_obj
                            video_info['date_ymd'] = date_obj.strftime('%Y%m%d')
                        
                        videos.append(video_info)
                        print(f"  Processed video {i}: {video_info['title'][:80]}...")
                    elif video_info:
                        print(f"  Warning: Video block {i} missing required fields")
            
            print(f"  Successfully parsed {len(videos)} videos")
            return channel_name, videos
            
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"  Error reading file: {e}")
            return None, []
    
    print(f"  Failed to read file with any encoding")
    return None, []

def create_rss_feed(channel_name, videos, output_file=None):
    """Create RSS feed XML from videos data."""
    if not videos:
        print("  No videos to create RSS feed")
        return None
    
    if not output_file:
        # Create output filename based on channel name
        safe_name = re.sub(r'[^\w\-_]', '_', channel_name.lower())
        output_file = f"{safe_name}_feed.xml"
    
    # Current date for lastBuildDate
    current_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    # Create the root element with namespaces
    rss = ET.Element('rss', {
        'version': '2.0',
        'xmlns:atom': 'http://www.w3.org/2005/Atom',
        'xmlns:content': 'http://purl.org/rss/1.0/modules/content/',
        'xmlns:media': 'http://search.yahoo.com/mrss/'
    })
    
    # Create channel element
    channel = ET.SubElement(rss, 'channel')
    
    # Channel metadata
    ET.SubElement(channel, 'title').text = f"{channel_name} - TikTok"
    ET.SubElement(channel, 'link').text = f"https://urlebird.com/user/{channel_name.lower().replace(' ', '.')}/"
    ET.SubElement(channel, 'description').text = f"TikTok videos from {channel_name}"
    
    # Self link
    atom_link = ET.SubElement(channel, 'atom:link', {
        'href': f"https://raw.githubusercontent.com/user/rss/main/{output_file}",
        'rel': 'self'
    })
    
    ET.SubElement(channel, 'docs').text = 'http://www.rssboard.org/rss-specification'
    ET.SubElement(channel, 'generator').text = 'Urlebird HTML to RSS Converter'
    ET.SubElement(channel, 'language').text = 'en'
    ET.SubElement(channel, 'lastBuildDate').text = current_date
    
    # Add items for each video
    for video in videos:
        item = ET.SubElement(channel, 'item')
        
        # Escape title for XML (use the full title)
        safe_title = escape_xml(video['title'])
        ET.SubElement(item, 'title').text = safe_title
        
        # Video link
        ET.SubElement(item, 'link').text = video['link']
        
        # Create description with thumbnail image and stats
        description_parts = []
        
        if 'image' in video:
            description_parts.append(f'<img src="{video["image"]}" alt="{safe_title}" />')
        
        description_parts.append(f'<p>{safe_title}</p>')
        
        # Add stats if available
        stats_text = []
        if 'views' in video:
            stats_text.append(f'Views: {video["views"]}')
        if 'likes' in video:
            stats_text.append(f'Likes: {video["likes"]}')
        if 'comments' in video:
            stats_text.append(f'Comments: {video["comments"]}')
        
        if stats_text:
            description_parts.append(f'<p>{" | ".join(stats_text)}</p>')
        
        # Join description parts and escape XML
        description_text = ''.join(description_parts)
        description_text = escape_xml(description_text)
        ET.SubElement(item, 'description').text = description_text
        
        # Add CDATA section for description to preserve HTML
        # Remove the existing description element and add a new one with CDATA
        for elem in item.findall('description'):
            item.remove(elem)
        
        # Create description with CDATA
        description_elem = ET.SubElement(item, 'description')
        description_elem.text = '<![CDATA[' + ''.join(description_parts) + ']]>'
        
        # Add media content
        if 'image' in video:
            media_content = ET.SubElement(item, 'media:content', {
                'url': video['image'],
                'type': 'image/jpeg',
                'medium': 'image'
            })
            ET.SubElement(media_content, 'media:title').text = safe_title
        
        # GUID (use video link)
        guid = ET.SubElement(item, 'guid', {'isPermaLink': 'true'})
        guid.text = video['link']
        
        # Publication date
        pub_date = format_rfc2822(video['date_obj'])
        ET.SubElement(item, 'pubDate').text = pub_date
    
    # Convert to string with pretty printing
    xml_string = ET.tostring(rss, encoding='unicode')
    
    # Use minidom for pretty printing
    dom = minidom.parseString(xml_string)
    pretty_xml = dom.toprettyxml(indent='  ')
    
    # Remove extra newlines added by toprettyxml
    lines = pretty_xml.split('\n')
    lines = [line for line in lines if line.strip()]
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        # Write XML declaration
        f.write('<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n')
        # Write the rest of the XML
        f.write('\n'.join(lines[1:]))  # Skip the XML declaration from minidom
    
    return output_file

def main():
    """Main function to run the script."""
    print("=" * 60)
    print("Urlebird HTML to RSS Converter")
    print("=" * 60)
    
    # Find HTML files
    html_files = find_html_files()
    
    if not html_files:
        print("\nError: No HTML files (.htm or .html) found in the current directory.")
        print("Please make sure there's at least one HTML file to process.")
        return
    
    # If multiple files, let user choose
    if len(html_files) > 1:
        print(f"\nFound {len(html_files)} HTML files:")
        for i, file in enumerate(html_files, 1):
            print(f"  {i}. {file}")
        
        try:
            choice = int(input(f"\nSelect file to process (1-{len(html_files)}): ").strip())
            if 1 <= choice <= len(html_files):
                input_file = html_files[choice - 1]
            else:
                print("Invalid selection. Using first file.")
                input_file = html_files[0]
        except ValueError:
            print("Invalid input. Using first file.")
            input_file = html_files[0]
    else:
        input_file = html_files[0]
    
    print(f"\nProcessing file: {input_file}")
    
    # Read and parse HTML file
    print(f"Reading '{input_file}'...")
    channel_name, videos = read_html_file(input_file)
    
    if not videos:
        print("No valid videos found. Exiting.")
        return
    
    print(f"\nFound channel: {channel_name}")
    print(f"Found {len(videos)} valid videos.")
    
    # Ask for channel name confirmation/override
    user_channel = input(f"\nEnter channel name (press Enter to use '{channel_name}'): ").strip()
    if user_channel:
        channel_name = user_channel
    
    # Ask for output filename
    default_output = f"{channel_name.lower().replace(' ', '_')}_feed.xml"
    output_file = input(f"\nEnter output filename (press Enter for default '{default_output}'): ").strip()
    if not output_file:
        output_file = default_output
    
    # Create RSS feed
    print(f"\nCreating RSS feed...")
    created_file = create_rss_feed(channel_name, videos, output_file)
    
    if created_file:
        print(f"\n✓ RSS feed created successfully!")
        print(f"  Output file: {created_file}")
        print(f"  Channel: {channel_name}")
        print(f"  Videos included: {len(videos)}")
        
        # Show a sample of the first item
        if videos:
            print(f"\nSample item:")
            print(f"  Title: {videos[0]['title'][:100]}...")
            print(f"  Link: {videos[0]['link'][:60]}...")
            if 'image' in videos[0]:
                print(f"  Thumbnail: {videos[0]['image'][:60]}...")
            if 'relative_date' in videos[0]:
                print(f"  Relative date: {videos[0]['relative_date']}")
            print(f"  Calculated date: {format_rfc2822(videos[0]['date_obj'])}")
    else:
        print("\n✗ Failed to create RSS feed.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
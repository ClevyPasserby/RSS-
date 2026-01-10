#!/usr/bin/env python3
"""
RSS Feed Generator from channel_videos.txt
Creates an RSS feed with YouTube embed links from a text file containing video data.
"""

import os
import sys
import xml.etree.ElementTree as ET
import re
from datetime import datetime
from xml.dom import minidom

def parse_line(line):
    """Parse a line from channel_videos.txt to extract ID, Title, and Date."""
    # Remove any leading/trailing whitespace
    line = line.strip()
    if not line:
        return None
    
    # Try to extract ID, Title, and Date using regex pattern
    # Pattern looks for "ID: <id> | Title: <title> | Date: <date>"
    pattern = r'ID:\s*(.+?)\s*\|\s*Title:\s*(.+?)\s*\|\s*Date:\s*(\d{8})'
    match = re.search(pattern, line)
    
    if match:
        video_id = match.group(1).strip()
        title = match.group(2).strip()
        date_str = match.group(3).strip()
        
        return {
            'id': video_id,
            'title': title,
            'date': date_str
        }
    
    return None

def format_rfc2822(date_str):
    """Convert YYYYMMDD date to RFC 2822 format."""
    try:
        # Parse the date string
        dt = datetime.strptime(date_str, '%Y%m%d')
        # Format to RFC 2822 (with time set to 00:00:00)
        return dt.strftime('%a, %d %b %Y 00:00:00 +0000')
    except ValueError:
        # If date parsing fails, use current date
        return datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')

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

def read_channel_videos(filename):
    """Read and parse channel_videos.txt file."""
    videos = []
    lines_read = 0
    
    # Try different encodings to handle various text files
    encodings = ['utf-8', 'latin-1', 'cp1252', 'utf-16']
    
    for encoding in encodings:
        try:
            with open(filename, 'r', encoding=encoding) as file:
                for line in file:
                    lines_read += 1
                    parsed = parse_line(line)
                    if parsed:
                        videos.append(parsed)
                    else:
                        print(f"  Warning: Could not parse line {lines_read}: {line[:50]}...")
            break  # If we successfully read the file, break out of the loop
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found.")
            return []
    
    if not videos:
        print(f"  No valid videos found in {filename}.")
        if lines_read == 0:
            print(f"  File might be empty or in an unexpected format.")
    
    return videos

def create_rss_feed(channel_name, videos, output_file=None):
    """Create RSS feed XML from videos data."""
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
        'xmlns:content': 'http://purl.org/rss/1.0/modules/content/'
    })
    
    # Create channel element
    channel = ET.SubElement(rss, 'channel')
    
    # Channel metadata
    ET.SubElement(channel, 'title').text = f"{channel_name} YouTube"
    ET.SubElement(channel, 'link').text = f"https://raw.githubusercontent.com/user/rss/main/{output_file}"
    ET.SubElement(channel, 'description').text = f"All the latest videos from {channel_name}"
    
    # Self link
    atom_link = ET.SubElement(channel, 'atom:link', {
        'href': f"https://raw.githubusercontent.com/user/rss/main/{output_file}",
        'rel': 'self'
    })
    
    ET.SubElement(channel, 'docs').text = 'http://www.rssboard.org/rss-specification'
    ET.SubElement(channel, 'generator').text = 'Custom Python RSS Generator'
    ET.SubElement(channel, 'language').text = 'en'
    ET.SubElement(channel, 'lastBuildDate').text = current_date
    
    # Create image element
    image = ET.SubElement(channel, 'image')
    ET.SubElement(image, 'url').text = 'https://raw.githubusercontent.com/user/rss/main/youtube-rss.png'
    ET.SubElement(image, 'title').text = f"{channel_name} YouTube"
    ET.SubElement(image, 'link').text = f"https://raw.githubusercontent.com/user/rss/main/{output_file}"
    
    # Add items for each video
    for video in videos:
        item = ET.SubElement(channel, 'item')
        
        # Escape title for XML
        safe_title = escape_xml(video['title'])
        ET.SubElement(item, 'title').text = safe_title
        
        # Create YouTube embed link
        video_link = f"https://www.youtube-nocookie.com/embed/{video['id']}"
        ET.SubElement(item, 'link').text = video_link
        
        # Create description with thumbnail image and title
        thumbnail_url = f"https://img.youtube.com/vi/{video['id']}/maxresdefault.jpg"
        description = f'&lt;img src="{thumbnail_url}" /&gt; {safe_title}'
        ET.SubElement(item, 'description').text = description
        
        # GUID (use video link as permanent link)
        guid = ET.SubElement(item, 'guid', {'isPermaLink': 'false'})
        guid.text = video_link
        
        # Publication date
        pub_date = format_rfc2822(video['date'])
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
    print("RSS Feed Generator")
    print("=" * 60)
    
    # Ask for channel name
    channel_name = input("Enter the channel name: ").strip()
    if not channel_name:
        print("Error: Channel name cannot be empty.")
        return
    
    # Check if channel_videos.txt exists
    input_file = 'channel_videos.txt'
    if not os.path.exists(input_file):
        print(f"\nError: '{input_file}' not found in the current directory.")
        print(f"Please make sure '{input_file}' exists with the following format:")
        print("  ID: VIDEO_ID | Title: VIDEO_TITLE | Date: YYYYMMDD")
        return
    
    print(f"\nReading '{input_file}'...")
    videos = read_channel_videos(input_file)
    
    if not videos:
        print("No valid videos to process. Exiting.")
        return
    
    print(f"Found {len(videos)} valid videos.")
    
    # Ask for output filename (optional)
    output_file = input(f"\nEnter output filename (press Enter for default '{channel_name.lower().replace(' ', '_')}_feed.xml'): ").strip()
    if not output_file:
        output_file = None
    
    # Create RSS feed
    print(f"\nCreating RSS feed...")
    created_file = create_rss_feed(channel_name, videos, output_file)
    
    print(f"\n✓ RSS feed created successfully!")
    print(f"  Output file: {created_file}")
    print(f"  Channel: {channel_name}")
    print(f"  Videos included: {len(videos)}")
    
    # Show a sample of the first item
    if videos:
        print(f"\nSample item:")
        print(f"  Title: {videos[0]['title'][:50]}...")
        print(f"  Link: https://www.youtube-nocookie.com/embed/{videos[0]['id']}")
        print(f"  Thumbnail: https://img.youtube.com/vi/{videos[0]['id']}/maxresdefault.jpg")
        print(f"  Date: {format_rfc2822(videos[0]['date'])}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)
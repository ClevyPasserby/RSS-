import subprocess
import re
import time
import os
import sys
from datetime import datetime
from pathlib import Path

class YouTubeChannelTracker:
    def __init__(self):
        self.log_file = "logs.txt"
        self.channel_url = "https://www.youtube.com/@mikxqs"
        self.base_output = "channel_videos.txt"
        self.temp_file = "temp.txt"
        self.restricted_file = "Restricted.txt"
        self.current_temp = None
        self.restricted_ids = set()
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_header = f"\n{'='*60}\nSession started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*60}\n"
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_header)
    
    def log_message(self, message, level="INFO"):
        """Log message to log file and print to console"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        print(log_entry)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + "\n")
    
    def extract_video_id(self, line, pattern_type="error"):
        """Extract video ID from log line"""
        patterns = {
            "error": r'ERROR: \[youtube\] ([A-Za-z0-9_-]+):',
            "warning": r'WARNING: \[youtube\] ([A-Za-z0-9_-]+):'
        }
        
        if pattern_type in patterns:
            match = re.search(patterns[pattern_type], line)
            if match:
                return match.group(1)
        return None
    
    def extract_success_line(self, line):
        """Extract successful video info line"""
        if line.startswith("ID:"):
            return line.strip()
        return None
    
    def is_restricted_error(self, line):
        """Check if line contains age restriction error"""
        return "Sign in to confirm your age" in line and "inappropriate for some users" in line
    
    def add_to_restricted(self, video_id):
        """Add video ID to restricted file"""
        if video_id in self.restricted_ids:
            return
        
        self.restricted_ids.add(video_id)
        
        # Write to Restricted.txt
        with open(self.restricted_file, 'a', encoding='utf-8') as f:
            f.write(f"{video_id}\n")
        
        self.log_message(f"Added {video_id} to {self.restricted_file} (age-restricted video)", "RESTRICTED")
    
    def check_existing_temp(self):
        """Check for existing temp files and return the latest one"""
        temp_files = list(Path('.').glob('temp*.txt'))
        if not temp_files:
            return None
        
        # Sort by modification time
        temp_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return str(temp_files[0])
    
    def read_temp_ids(self, temp_file):
        """Read video IDs from temp file"""
        if not os.path.exists(temp_file):
            return []
        
        with open(temp_file, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    
    def update_temp_file(self, temp_file, ids):
        """Update temp file with remaining IDs"""
        if not ids:
            if os.path.exists(temp_file):
                self.log_message(f"Removing empty temp file: {temp_file}")
                os.remove(temp_file)
            return
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            for video_id in ids:
                f.write(f"{video_id}\n")
        self.log_message(f"Updated {temp_file} with {len(ids)} IDs")
    
    def get_next_output_file(self):
        """Get the next available output file name"""
        base_name = "channel_videos"
        extension = ".txt"
        counter = 1
        
        while True:
            if counter == 1:
                filename = f"{base_name}{extension}"
            else:
                filename = f"{base_name}({counter}){extension}"
            
            if not os.path.exists(filename):
                return filename, counter
            counter += 1
    
    def run_command(self, command, output_file=None, append=False):
        """Run a command and process output in real-time"""
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        return process
    
    def process_initial_channel(self):
        """Process the initial channel command"""
        output_file, file_num = self.get_next_output_file()
        self.log_message(f"Starting initial channel processing to {output_file}")
        
        command = f'yt-dlp --skip-download --print "ID: %(id)s | Title: %(title)s | Date: %(upload_date)s" "{self.channel_url}" > "{output_file}"'
        self.log_message(f"Running command: {command}")
        
        errored_ids = []
        process = self.run_command(command)
        
        last_activity = time.time()
        progress_timeout = 300  # 5 minutes without output
        
        # Read output in real-time
        while True:
            output = process.stdout.readline()
            
            if output:
                last_activity = time.time()
                
                # Log all output
                if output.strip():
                    self.log_message(output.strip(), "YT-DLP")
                
                # Check for errors
                if "ERROR: [youtube]" in output:
                    video_id = self.extract_video_id(output, "error")
                    if video_id:
                        if self.is_restricted_error(output):
                            # Add to restricted file and skip
                            self.add_to_restricted(video_id)
                        elif video_id not in errored_ids:
                            errored_ids.append(video_id)
                            self.log_message(f"Found errored ID: {video_id}", "ERROR")
                
            # Check for process completion
            retcode = process.poll()
            if retcode is not None:
                # Read any remaining output
                remaining_output = process.stdout.read()
                for line in remaining_output.split('\n'):
                    if line.strip():
                        self.log_message(line.strip(), "YT-DLP")
                        if "ERROR: [youtube]" in line:
                            video_id = self.extract_video_id(line, "error")
                            if video_id:
                                if self.is_restricted_error(line):
                                    # Add to restricted file and skip
                                    self.add_to_restricted(video_id)
                                elif video_id not in errored_ids:
                                    errored_ids.append(video_id)
                                    self.log_message(f"Found errored ID: {video_id}", "ERROR")
                break
            
            # Check for timeout (no output for too long)
            if time.time() - last_activity > progress_timeout:
                self.log_message("No output for 5 minutes, assuming process stuck", "WARNING")
                process.terminate()
                time.sleep(5)
                if process.poll() is None:
                    process.kill()
                break
        
        # Save errored IDs to temp file (excluding restricted ones)
        if errored_ids:
            temp_name = "temp.txt"
            with open(temp_name, 'w', encoding='utf-8') as f:
                for video_id in errored_ids:
                    f.write(f"{video_id}\n")
            self.log_message(f"Saved {len(errored_ids)} errored IDs to {temp_name}")
            return temp_name, file_num, True
        else:
            self.log_message("No errors found during initial processing", "SUCCESS")
            return None, file_num, False
    
    def process_errored_ids(self, temp_file, start_file_num):
        """Process errored IDs from temp file"""
        self.log_message(f"Starting to process errored IDs from {temp_file}")
        
        video_ids = self.read_temp_ids(temp_file)
        if not video_ids:
            self.log_message(f"No IDs found in {temp_file}")
            return None
        
        remaining_ids = video_ids.copy()
        all_succeeded = True
        current_temp = temp_file
        iteration = 1
        
        while remaining_ids:
            self.log_message(f"Iteration {iteration} - Processing {len(remaining_ids)} IDs")
            
            # Create new output file for this session
            output_file, file_num = self.get_next_output_file()
            if file_num <= start_file_num:
                file_num = start_file_num + 1
                output_file = f"channel_videos({file_num}).txt"
            
            self.log_message(f"Using output file: {output_file}")
            
            # Process each ID
            for video_id in remaining_ids.copy():
                self.log_message(f"Processing ID: {video_id}")
                
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                command = f'yt-dlp --skip-download --print "ID: %(id)s | Title: %(title)s | Date: %(upload_date)s" "{video_url}"'
                
                process = self.run_command(command)
                succeeded = False
                has_error = False
                is_restricted = False
                
                # Process output in real-time
                while True:
                    output = process.stdout.readline()
                    if output:
                        output = output.strip()
                        if output:
                            self.log_message(output, "YT-DLP")
                            
                            # Check for success (video info line)
                            success_line = self.extract_success_line(output)
                            if success_line:
                                # Append to output file
                                with open(output_file, 'a', encoding='utf-8') as f:
                                    f.write(f"{success_line}\n")
                                self.log_message(f"Successfully processed {video_id}")
                                succeeded = True
                            
                            # Check for warning with this ID (considered success)
                            elif f"[youtube] {video_id}:" in output and "WARNING" in output:
                                self.log_message(f"Video {video_id} available with warnings", "WARNING")
                                succeeded = True
                            
                            # Check for age restriction error
                            elif "ERROR: [youtube]" in output and video_id in output and self.is_restricted_error(output):
                                self.log_message(f"Video {video_id} is age-restricted", "RESTRICTED")
                                self.add_to_restricted(video_id)
                                is_restricted = True
                                break  # Skip this video immediately
                            
                            # Check for other errors with this ID
                            elif "ERROR: [youtube]" in output and video_id in output:
                                has_error = True
                                self.log_message(f"Video {video_id} still errored", "ERROR")
                    
                    # Check for process completion
                    retcode = process.poll()
                    if retcode is not None:
                        break
                
                # Update tracking based on result
                if succeeded:
                    remaining_ids.remove(video_id)
                    self.update_temp_file(current_temp, remaining_ids)
                elif is_restricted:
                    # Remove from remaining IDs (skip this video)
                    if video_id in remaining_ids:
                        remaining_ids.remove(video_id)
                        self.update_temp_file(current_temp, remaining_ids)
                    self.log_message(f"Skipped age-restricted video: {video_id}")
                elif has_error:
                    all_succeeded = False
                    self.log_message(f"Waiting 60 seconds before next attempt due to error with {video_id}")
                    time.sleep(60)
                else:
                    # No clear result, assume error and retry
                    self.log_message(f"No clear result for {video_id}, treating as error", "WARNING")
                    all_succeeded = False
                    time.sleep(60)
            
            # Update iteration count
            iteration += 1
            
            # If all succeeded, we're done
            if not remaining_ids:
                self.log_message(f"All IDs from {temp_file} processed successfully")
                if os.path.exists(current_temp):
                    os.remove(current_temp)
                break
            
            # If we still have errors, create new temp file and continue
            if remaining_ids:
                all_succeeded = False
                new_temp = f"temp({iteration}).txt"
                with open(new_temp, 'w', encoding='utf-8') as f:
                    for video_id in remaining_ids:
                        f.write(f"{video_id}\n")
                
                self.log_message(f"Created new temp file: {new_temp} with {len(remaining_ids)} IDs")
                
                # Remove old temp file if it exists and is different
                if current_temp != temp_file and os.path.exists(current_temp):
                    os.remove(current_temp)
                
                current_temp = new_temp
                self.log_message("Starting next iteration after 60 seconds")
                time.sleep(60)
        
        return current_temp if not all_succeeded else None
    
    def report_restricted_videos(self):
        """Report restricted videos found during processing"""
        if os.path.exists(self.restricted_file):
            with open(self.restricted_file, 'r', encoding='utf-8') as f:
                restricted_ids = [line.strip() for line in f if line.strip()]
            
            if restricted_ids:
                self.log_message(f"Found {len(restricted_ids)} age-restricted video(s):", "INFO")
                for vid in restricted_ids:
                    self.log_message(f"  - {vid}", "INFO")
                self.log_message(f"Restricted video IDs have been saved to {self.restricted_file}", "INFO")
                return True
        return False
    
    def run(self):
        """Main execution loop"""
        self.log_message("Starting YouTube Channel Tracker")
        
        # Check for existing temp files
        existing_temp = self.check_existing_temp()
        
        if existing_temp:
            self.log_message(f"Found existing temp file: {existing_temp}")
            
            # Determine starting file number
            existing_files = list(Path('.').glob('channel_videos*.txt'))
            if existing_files:
                # Extract numbers from existing files
                numbers = []
                for file in existing_files:
                    match = re.search(r'channel_videos(?:\((\d+)\))?\.txt', str(file))
                    if match:
                        num = match.group(1)
                        numbers.append(int(num) if num else 1)
                start_file_num = max(numbers) if numbers else 1
            else:
                start_file_num = 1
            
            # Process existing temp file
            result_temp = self.process_errored_ids(existing_temp, start_file_num)
            
            if result_temp:
                self.log_message(f"Processing completed with remaining errors in {result_temp}")
            else:
                self.log_message("All errors resolved successfully")
        else:
            # Run initial channel processing
            temp_file, file_num, has_errors = self.process_initial_channel()
            
            if has_errors and temp_file:
                self.log_message("Starting error recovery process")
                self.process_errored_ids(temp_file, file_num)
        
        # Report restricted videos
        if self.report_restricted_videos():
            self.log_message("Note: Age-restricted videos were skipped and logged in Restricted.txt", "INFO")
        
        self.log_message("YouTube Channel Tracker completed")

def main():
    """Main function"""
    tracker = YouTubeChannelTracker()
    
    try:
        tracker.run()
    except KeyboardInterrupt:
        tracker.log_message("Script interrupted by user", "WARNING")
    except Exception as e:
        tracker.log_message(f"Unexpected error: {str(e)}", "ERROR")
        import traceback
        tracker.log_message(traceback.format_exc(), "ERROR")
    
    tracker.log_message("Script ended")

if __name__ == "__main__":
    main()
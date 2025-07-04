# Enhanced CSV Image Downloader

A powerful and intelligent web scraper for downloading product images and data from e-commerce websites.

## Features

- **Intelligent Image Detection**: Automatically finds and downloads product images using multiple strategies
- **Parallel Processing**: Downloads multiple products simultaneously for faster operation
- **Adaptive Performance**: Adjusts batch size and worker count based on success rates
- **Robust Error Handling**: Automatically retries failed downloads with intelligent backoff
- **Memory Management**: Optimized memory usage for long-running operations
- **Caching**: URL caching to avoid redundant downloads
- **Detailed Statistics**: Comprehensive statistics and progress tracking
- **User-friendly GUI**: Easy-to-use graphical interface

## Requirements

- Python 3.7+
- Chrome browser installed
- Required Python packages:
  - requests
  - selenium
  - webdriver_manager
  - Pillow
  - tqdm
  - tkinter (for GUI)

## Installation

1. Clone or download this repository
2. Install required packages:
   ```
   pip install requests selenium webdriver_manager Pillow tqdm
   ```

## Usage

### GUI Mode

Run the GUI application:

```
python scraper_gui.py
```

1. Select your CSV file containing product URLs
2. Configure the output directory and settings
3. Click "Start Scraping" to begin

### Command Line Mode

Run the command-line version:

```
python enhanced_csv_downloader.py --csv your_file.csv
```

## CSV Format

The CSV file should contain at least these columns:

- A URL column (containing product URLs)
- A Category column (for organizing downloaded images)
- An ID column (for naming the downloaded files)

## Configuration

The scraper can be configured by modifying the `Config` class in `enhanced_csv_downloader.py` or through the GUI:

- `MAX_WORKERS`: Number of parallel downloads (default: 10)
- `BATCH_SIZE`: Number of products to process in each batch (default: 20)
- `SELENIUM_TIMEOUT`: Timeout for page loading in seconds (default: 10)
- `MAX_RETRIES`: Maximum number of retry attempts (default: 2)
- And many more options...

## Recent Fixes

### localStorage Error Fix

We've implemented several improvements to handle the "Failed to read the 'localStorage' property from 'Window'" error:

1. **Disabled localStorage in Chrome**:

   - Added `dom.storage.enabled: False` to Chrome preferences
   - Added `--disable-web-security` and other flags to Chrome options

2. **Safe JavaScript Execution**:

   - Added `safe_execute_script` method to handle localStorage errors gracefully
   - Added checks for data: URLs before executing JavaScript
   - Wrapped JavaScript code in try/catch blocks

3. **Improved Page Loading**:

   - Added detection and handling of data: URL redirects
   - Removed localStorage/sessionStorage clearing that was causing errors
   - Added more robust error handling during page loading

4. **Enhanced Error Recovery**:
   - Added automatic retries for failed products
   - Added better error categorization
   - Implemented adaptive cooldown periods

## Troubleshooting

If you encounter issues:

1. **Timeout errors**: Increase the `SELENIUM_TIMEOUT` value
2. **Memory issues**: Reduce `MAX_WORKERS` and `BATCH_SIZE`
3. **Missing images**: Check that the product pages actually contain images
4. **Browser errors**: Ensure Chrome is properly installed and updated
5. **localStorage errors**: Make sure you're using the latest version with the fixes described above

## License

This project is licensed under the MIT License - see the LICENSE file for details.
# WebScraper_PlayWright

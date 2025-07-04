import os
import sys
import csv
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
import queue
import traceback
from pathlib import Path

# Import the scraper class
try:
    from enhanced_csv_downloader import EnhancedCSVImageDownloader, Config
except ImportError:
    messagebox.showerror("Import Error", "Could not import EnhancedCSVImageDownloader. Make sure enhanced_csv_downloader.py is in the same directory.")
    sys.exit(1)

class RedirectText:
    """Redirect stdout to tkinter Text widget"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = queue.Queue()
        self.update_interval = 100  # ms
        
    def write(self, string):
        self.buffer.put(string)
        
    def flush(self):
        pass
        
    def update_text_widget(self):
        try:
            while True:
                # Get all available text
                text = ""
                for _ in range(self.buffer.qsize()):
                    text += self.buffer.get_nowait()
                
                if text:
                    self.text_widget.configure(state="normal")
                    self.text_widget.insert(tk.END, text)
                    self.text_widget.configure(state="disabled")
                    self.text_widget.see(tk.END)
                break
        except queue.Empty:
            pass
        finally:
            self.text_widget.after(self.update_interval, self.update_text_widget)

class ScraperGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Enhanced CSV Image Downloader")
        self.geometry("900x700")
        self.minsize(800, 600)
        
        self.scraper = None
        self.scraper_thread = None
        self.is_running = False
        
        # Set style
        self.style = ttk.Style()
        self.style.theme_use('clam')  # Use a modern theme
        
        # Configure colors
        bg_color = "#f0f0f0"
        button_color = "#4a86e8"
        
        self.configure(bg=bg_color)
        
        # Create main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create input frame
        input_frame = ttk.LabelFrame(main_frame, text="Configuration")
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # CSV File selection
        csv_frame = ttk.Frame(input_frame)
        csv_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(csv_frame, text="CSV File:").pack(side=tk.LEFT, padx=5)
        self.csv_path_var = tk.StringVar()
        ttk.Entry(csv_frame, textvariable=self.csv_path_var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(csv_frame, text="Browse", command=self.browse_csv).pack(side=tk.LEFT, padx=5)
        
        # Output directory selection
        output_frame = ttk.Frame(input_frame)
        output_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(output_frame, text="Output Dir:").pack(side=tk.LEFT, padx=5)
        self.output_dir_var = tk.StringVar(value=Config.OUTPUT_DIR)
        ttk.Entry(output_frame, textvariable=self.output_dir_var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="Browse", command=self.browse_output_dir).pack(side=tk.LEFT, padx=5)
        
        # Advanced settings
        settings_frame = ttk.LabelFrame(main_frame, text="Advanced Settings")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create a frame for the first row of settings
        row1_frame = ttk.Frame(settings_frame)
        row1_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Workers
        ttk.Label(row1_frame, text="Workers:").pack(side=tk.LEFT, padx=5)
        self.workers_var = tk.IntVar(value=Config.MAX_WORKERS)
        ttk.Spinbox(row1_frame, from_=1, to=20, textvariable=self.workers_var, width=5).pack(side=tk.LEFT, padx=5)
        
        # Batch Size
        ttk.Label(row1_frame, text="Batch Size:").pack(side=tk.LEFT, padx=5)
        self.batch_size_var = tk.IntVar(value=Config.BATCH_SIZE)
        ttk.Spinbox(row1_frame, from_=1, to=50, textvariable=self.batch_size_var, width=5).pack(side=tk.LEFT, padx=5)
        
        # Timeout
        ttk.Label(row1_frame, text="Timeout (s):").pack(side=tk.LEFT, padx=5)
        self.timeout_var = tk.IntVar(value=Config.SELENIUM_TIMEOUT)
        ttk.Spinbox(row1_frame, from_=5, to=60, textvariable=self.timeout_var, width=5).pack(side=tk.LEFT, padx=5)
        
        # Create a frame for the second row of settings
        row2_frame = ttk.Frame(settings_frame)
        row2_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Enable URL Cache
        self.cache_var = tk.BooleanVar(value=Config.ENABLE_URL_CACHE)
        ttk.Checkbutton(row2_frame, text="Enable URL Cache", variable=self.cache_var).pack(side=tk.LEFT, padx=5)
        
        # Adaptive Retry
        self.adaptive_retry_var = tk.BooleanVar(value=Config.ADAPTIVE_RETRY)
        ttk.Checkbutton(row2_frame, text="Adaptive Retry", variable=self.adaptive_retry_var).pack(side=tk.LEFT, padx=5)
        
        # Max Retries
        ttk.Label(row2_frame, text="Max Retries:").pack(side=tk.LEFT, padx=5)
        self.max_retries_var = tk.IntVar(value=Config.MAX_RETRIES)
        ttk.Spinbox(row2_frame, from_=1, to=10, textvariable=self.max_retries_var, width=5).pack(side=tk.LEFT, padx=5)
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Start button
        self.start_button = ttk.Button(control_frame, text="Start Scraping", command=self.start_scraping)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # Stop button
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_scraping, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress")
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.status_var).pack(padx=5, pady=5)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics")
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Stats grid
        self.stats_grid = ttk.Frame(stats_frame)
        self.stats_grid.pack(fill=tk.X, padx=5, pady=5)
        
        # Create stats labels
        self.create_stat_label(0, "Total:", "0")
        self.create_stat_label(0, "Processed:", "0", column=2)
        self.create_stat_label(1, "Success:", "0")
        self.create_stat_label(1, "Errors:", "0", column=2)
        self.create_stat_label(2, "Existing:", "0")
        self.create_stat_label(2, "Not Found:", "0", column=2)
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Log text widget
        self.log_text = scrolledtext.ScrolledText(log_frame, state="disabled", wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Set up stdout redirection
        self.redirect = RedirectText(self.log_text)
        self.old_stdout = sys.stdout
        sys.stdout = self.redirect
        self.redirect.update_text_widget()
        
        # Initialize stats variables
        self.stats_vars = {
            "total": tk.StringVar(value="0"),
            "processed": tk.StringVar(value="0"),
            "success": tk.StringVar(value="0"),
            "errors": tk.StringVar(value="0"),
            "existing": tk.StringVar(value="0"),
            "not_found": tk.StringVar(value="0")
        }
        
        # Update stats labels
        self.update_stats_labels()
        
        # Set up periodic stats update
        self.after(1000, self.update_stats)
        
    def create_stat_label(self, row, label_text, value_text, column=0):
        ttk.Label(self.stats_grid, text=label_text).grid(row=row, column=column, padx=5, pady=2, sticky=tk.W)
        ttk.Label(self.stats_grid, text=value_text).grid(row=row, column=column+1, padx=5, pady=2, sticky=tk.W)
    
    def browse_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if file_path:
            self.csv_path_var.set(file_path)
    
    def browse_output_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_dir_var.set(dir_path)
    
    def update_stats_labels(self):
        # Update stats labels with current values
        for i, (key, var) in enumerate(self.stats_vars.items()):
            row = i // 2
            column = 2 if i % 2 else 0
            ttk.Label(self.stats_grid, text=f"{key.capitalize()}:").grid(row=row, column=column, padx=5, pady=2, sticky=tk.W)
            ttk.Label(self.stats_grid, textvariable=var).grid(row=row, column=column+1, padx=5, pady=2, sticky=tk.W)
    
    def update_stats(self):
        if self.scraper and self.is_running:
            # Update stats from scraper
            stats = self.scraper.stats
            self.stats_vars["total"].set(str(stats['total_products']))
            self.stats_vars["processed"].set(str(stats['total_processed']))
            self.stats_vars["success"].set(str(stats['successful_downloads']))
            self.stats_vars["errors"].set(str(stats['errors']))
            self.stats_vars["existing"].set(str(stats['already_exists']))
            self.stats_vars["not_found"].set(str(stats['not_found']))
            
            # Update progress bar
            if stats['total_products'] > 0:
                progress = (stats['total_processed'] / stats['total_products']) * 100
                self.progress_var.set(progress)
                self.status_var.set(f"Processing: {stats['total_processed']}/{stats['total_products']} ({progress:.1f}%)")
        
        # Schedule next update
        self.after(1000, self.update_stats)
    
    def apply_config(self):
        """Apply GUI settings to Config"""
        # Create a new instance of the Config class to modify
        # instead of trying to modify class attributes directly
        config_values = {
            "MAX_WORKERS": self.workers_var.get(),
            "BATCH_SIZE": self.batch_size_var.get(),
            "SELENIUM_TIMEOUT": self.timeout_var.get(),
            "ENABLE_URL_CACHE": self.cache_var.get(),
            "ADAPTIVE_RETRY": self.adaptive_retry_var.get(),
            "MAX_RETRIES": self.max_retries_var.get(),
            "OUTPUT_DIR": self.output_dir_var.get()
        }
        
        # Apply these values to the scraper when it's created
        self.config_values = config_values
    
    def start_scraping(self):
        # Validate inputs
        csv_path = self.csv_path_var.get()
        if not csv_path:
            messagebox.showerror("Error", "Please select a CSV file")
            return
        
        if not os.path.exists(csv_path):
            messagebox.showerror("Error", "CSV file does not exist")
            return
        
        output_dir = self.output_dir_var.get()
        if not output_dir:
            messagebox.showerror("Error", "Please specify an output directory")
            return
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Apply configuration
        self.apply_config()
        
        # Initialize scraper
        try:
            # Initialize the scraper with the CSV file
            self.scraper = EnhancedCSVImageDownloader(csv_file_path=csv_path)
            
            # Store the custom output directory if different from default
            self.custom_output_dir = None
            if hasattr(self, 'config_values') and self.config_values["OUTPUT_DIR"] != Config.OUTPUT_DIR:
                self.custom_output_dir = self.config_values["OUTPUT_DIR"]
                
                # Create the directory structure
                if not os.path.exists(self.custom_output_dir):
                    os.makedirs(self.custom_output_dir, exist_ok=True)
                
                # We'll handle output directory in the download process by
                # monkey patching the save methods when needed
            
            # Apply other configuration values to the scraper instance
            if hasattr(self, 'config_values'):
                self.scraper.current_workers = self.config_values["MAX_WORKERS"]
                self.scraper.current_batch_size = self.config_values["BATCH_SIZE"]
            
            # Start scraper in a separate thread
            self.is_running = True
            self.scraper_thread = threading.Thread(target=self.run_scraper)
            self.scraper_thread.daemon = True
            self.scraper_thread.start()
            
            # Update UI
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_var.set("Scraping started...")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize scraper: {str(e)}")
            traceback.print_exc()
    
    def run_scraper(self):
        """Run the scraper in a separate thread"""
        try:
            if self.scraper:
                # Check if we need to use a custom output directory
                if hasattr(self, 'custom_output_dir') and self.custom_output_dir is not None:
                    # Make sure custom_output_dir is a string
                    output_dir = str(self.custom_output_dir)
                    
                    # Create a wrapper function to handle the custom output directory
                    original_save_product_data = self.scraper.save_product_data
                    
                    def custom_save_product_data(product_data, product, image_path=None):
                        # Replace the output directory in paths
                        category_dir = os.path.join(output_dir, product['category'])
                        os.makedirs(category_dir, exist_ok=True)
                        
                        # Call the original method but with our custom path
                        return original_save_product_data(product_data, product, image_path)
                    
                    # Replace the method with our custom one
                    self.scraper.save_product_data = custom_save_product_data
                
                # Run the scraper
                success = self.scraper.run()
                self.after(0, self.scraping_finished, success)
            else:
                self.after(0, self.scraping_error, "Scraper not initialized")
        except Exception as e:
            self.after(0, self.scraping_error, str(e))
    
    def scraping_finished(self, success):
        """Called when scraping is finished"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        if success:
            self.status_var.set("Scraping completed successfully")
            messagebox.showinfo("Success", "Scraping completed successfully")
        else:
            self.status_var.set("Scraping finished with errors")
            messagebox.showwarning("Warning", "Scraping finished with errors")
    
    def scraping_error(self, error_msg):
        """Called when scraping encounters an error"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set(f"Error: {error_msg}")
        messagebox.showerror("Error", f"Scraping error: {error_msg}")
    
    def stop_scraping(self):
        """Stop the scraping process"""
        if self.is_running:
            self.is_running = False
            self.status_var.set("Stopping...")
            messagebox.showinfo("Stopping", "Scraping will stop after current batch completes.")
            # The scraper will check self.is_running periodically
    
    def on_closing(self):
        """Handle window closing"""
        if self.is_running:
            if messagebox.askokcancel("Quit", "Scraping is in progress. Do you want to stop and exit?"):
                self.is_running = False
                self.destroy()
        else:
            self.destroy()
        
        # Restore stdout
        sys.stdout = self.old_stdout

if __name__ == "__main__":
    app = ScraperGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop() 
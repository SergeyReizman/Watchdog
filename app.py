import tkinter as tk
from tkinter import ttk
import threading
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import psutil

# Define a global error label to display error messages in the GUI
error_label = None

def read_config(config_file):
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            services_config = config.get('services', [])
            monitoring_interval = config.get('monitoring_interval_seconds', 60)
        return services_config, monitoring_interval
    except (FileNotFoundError, Exception) as e:
        # Display error messages in the GUI for better user feedback
        error_label.config(text=f"Error: {str(e)}", foreground="red")
        return [], 60

def send_notification(subject, message, email_sender, email_password, email_receiver):
    try:
        msg = MIMEMultipart()
        msg['From'] = email_sender
        msg['To'] = email_receiver
        msg['Subject'] = subject
        text = MIMEText(message)
        msg.attach(text)
        
        # Use context managers for SMTP connections to ensure they are properly closed
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp_server:
            smtp_server.starttls()
            smtp_server.login(email_sender, email_password)
            smtp_server.sendmail(email_sender, email_receiver, msg.as_string())
        
        # Provide user feedback for successful email sending
        success_label.config(text="Email sent successfully", foreground="green")
    except Exception as e:
        # Display error messages in the GUI and log them for debugging
        error_label.config(text=f"Error: {str(e)}", foreground="red")
        logging.error(f"Failed to send email notification: {str(e)}")

def check_service_with_dependencies(service_config, email_sender, email_password, email_receiver):
    service_name = service_config["name"]
    dependencies = service_config.get("dependencies", [])
    try:
        for dependency_name in dependencies:
            dependency_service = psutil.win_service_get(dependency_name)
            if dependency_service.status() != "running":
                # Notify about dependency issues
                logging.warning(f"Dependency {dependency_name} of {service_name} is not running.")
                send_notification(
                    f"Service Alert: Dependency {dependency_name} of {service_name} is not running",
                    f"The {dependency_name} service is not running, required by {service_name}.",
                    email_sender, email_password, email_receiver
                )
                return
        
        # Monitor and potentially restart the service
        service = psutil.win_service_get(service_name)
        previous_state = service.status()
        if previous_state == "running":
            logging.info(f"{service_name} is running.")
        else:
            logging.warning(f"{service_name} is not running. Attempting to restart...")
            try:
                service.restart()
                logging.info(f"Restarted {service_name} successfully.")
            except Exception as restart_error:
                # Display error messages in the GUI and log them
                error_label.config(text=f"Error: {str(restart_error)}", foreground="red")
                logging.error(f"Failed to restart {service_name}: {str(restart_error)}")
                send_notification(
                    f"Service Alert: {service_name} restart failed",
                    f"Failed to restart {service_name}: {str(restart_error)}",
                    email_sender, email_password, email_receiver
                )
        
        current_state = service.status()
        if previous_state != current_state:
            logging.info(f"{service_name} state changed from {previous_state} to {current_state}")
    except (psutil.NoSuchProcess, Exception) as e:
        # Display error messages in the GUI and log them
        error_label.config(text=f"Error: {str(e)}", foreground="red")
        logging.error(f"Error checking {service_name}: {str(e)}")

def start_monitoring():
    try:
        email_sender = sender_email_entry.get()
        email_password = sender_password_entry.get()
        email_receiver = recipient_email_entry.get()
        config_file = config_file_entry.get()
        
        # Start a separate monitoring thread
        monitoring_thread = threading.Thread(target=monitor_services,
                                             args=(email_sender, email_password, email_receiver, config_file))
        monitoring_thread.start()
        
        # Provide user feedback for successful monitoring start
        success_label.config(text="Monitoring started successfully", foreground="green")
    except Exception as e:
        # Display error messages in the GUI and log them
        error_label.config(text=f"Error: {str(e)}", foreground="red")
        logging.error(f"Error starting monitoring: {str(e)}")

def exit_program():
    # Signal the monitoring thread to exit and quit the GUI
    exit_event.set()
    root.quit()

def monitor_services(email_sender, email_password, email_receiver, config_file):
    while not exit_event.is_set():
        services_config, monitoring_interval = read_config(config_file)
        for service_config in services_config:
            check_service_with_dependencies(service_config, email_sender, email_password, email_receiver)
        time.sleep(monitoring_interval)

# Create the main GUI window
root = tk.Tk()
root.title("Service Monitoring GUI")

# Define StringVar variables for entry fields
sender_email_entry = tk.StringVar()
sender_password_entry = tk.StringVar()
recipient_email_entry = tk.StringVar()
config_file_entry = tk.StringVar()

# Define GUI elements (labels, entry fields, buttons)
elements = [
    ("Sender's Email:", sender_email_entry),
    ("Sender's Password:", sender_password_entry),
    ("Recipient's Email:", recipient_email_entry),
    ("Configuration File:", config_file_entry)
]

# Create and pack GUI elements
for label_text, entry_var in elements:
    label = ttk.Label(root, text=label_text)
    label.pack()
    entry = ttk.Entry(root, textvariable=entry_var)
    entry.pack()

buttons = [
    ("Start Monitoring", start_monitoring),
    ("Exit", exit_program)
]

for button_text, button_command in buttons:
    button = ttk.Button(root, text=button_text, command=button_command)
    button.pack()

# Create labels for displaying error and success messages
error_label = ttk.Label(root, text="", foreground="red")
error_label.pack()
success_label = ttk.Label(root, text="", foreground="green")
success_label.pack()

# Initialize an exit event for monitoring thread termination
exit_event = threading.Event()

if __name__ == "__main__":
    # Initialize logging to record monitoring events to a log file
    logging.basicConfig(filename='service_monitor.log', level=logging.INFO)
    # Start the main GUI loop
    root.mainloop()

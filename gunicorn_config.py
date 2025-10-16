# Gunicorn configuration file
# This extends the timeout to handle long-running blockchain operations

# Worker timeout (3 minutes = 180 seconds)
# This allows enough time for vesting contract deployment transactions
timeout = 180

# Bind address
bind = "0.0.0.0:5000"

# Reload on code changes
reload = True

# Reuse port (allows multiple instances)
reuse_port = True

# Worker class
worker_class = "sync"

# Number of workers
workers = 1

# Logging
loglevel = "debug"
accesslog = "-"
errorlog = "-"

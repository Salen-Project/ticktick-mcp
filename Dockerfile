FROM python:3.11-slim

WORKDIR /app

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the source
COPY . .

# Dummy credentials -- only used if a tool is actually called.
# The MCP server registers tools at import time and starts without
# needing real OAuth tokens, which allows Glama to inspect it.
ENV TICKTICK_CLIENT_ID=glama_inspection
ENV TICKTICK_CLIENT_SECRET=glama_inspection

# Expose stdio transport (default for MCP)
CMD ["python", "server.py"]

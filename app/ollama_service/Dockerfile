FROM ollama/ollama:latest

COPY app/ollama_service/start-ollama.sh /start-ollama.sh
# Expose the default Ollama port
EXPOSE 11434

# Use the startup script
ENTRYPOINT ["/start-ollama.sh"]
CMD ["pull", "gpt-oss:20b"]
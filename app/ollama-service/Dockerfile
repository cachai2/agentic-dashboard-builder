# Ollama service container exposes the API on port 11434.
FROM ollama/ollama:0.12.6

ENV OLLAMA_HOST=0.0.0.0 \
	OLLAMA_ORIGINS="*"

EXPOSE 11434

ENTRYPOINT ["ollama"]
CMD ["serve"]

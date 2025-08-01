# Use the official VOICEVOX engine image
FROM voicevox/voicevox_engine:cpu-ubuntu20.04-latest

# Install the missing web server libraries
RUN /opt/python/bin/python3 -m pip install uvicorn gunicorn

# Expose the port the server runs on
EXPOSE 50021

# Add a health check to give the app a 5-minute grace period to start
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
  CMD curl --fail http://localhost:50021/version || exit 1

# Run the server in the background (&) and keep the container alive
CMD /opt/python/bin/python3 ./run.py --voicelib_dir /opt/voicevox_core/ --runtime_dir /opt/onnxruntime/lib --host 0.0.0.0 --cors_policy_mode all & tail -f /dev/null

module.exports = {
  apps: [
    {
      name: "nexclip-backend",
      script: "../venv/bin/uvicorn",
      args: "app.main:app --host 0.0.0.0 --port 8000",
      cwd: "./backend",
      interpreter: "none",
      env: {
        APP_ENV: "production",
      }
    },
    {
      name: "nexclip-celery",
      script: "../venv/bin/celery",
      args: "-A app.workers.celery_app worker --loglevel=info --concurrency=4 -Q video,captions,nexearch,celery",
      cwd: "./backend",
      interpreter: "none",
      env: {
        APP_ENV: "production",
      }
    },
    {
      name: "nexclip-nex-agent",
      script: "../venv/bin/python",
      args: "server.py",
      cwd: "./nex_agent",
      interpreter: "none",
      env: {
        APP_ENV: "production",
      }
    },
    {
      name: "nexclip-nexearch",
      script: "venv/bin/uvicorn",
      args: "nexearch.main:app --host 0.0.0.0 --port 8002",
      cwd: ".",
      interpreter: "none",
      env: {
        APP_ENV: "production",
      }
    },
    {
      name: "nexclip-arc-agent",
      script: "../../venv/bin/python",
      args: "server.py",
      cwd: "./nexearch/arc",
      interpreter: "none",
      env: {
        APP_ENV: "production",
      }
    },
    {
      name: "nexclip-frontend",
      script: "npm",
      args: "start",
      cwd: "./frontend",
      interpreter: "none",
      env: {
        NODE_ENV: "production",
        PORT: 3000
      }
    }
  ]
};

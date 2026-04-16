![Lint](https://github.com/swe-students-spring2026/4-containers-design_ant-4/actions/workflows/lint.yml/badge.svg)
![ML Client Tests](https://github.com/swe-students-spring2026/4-containers-design_ant-4/actions/workflows/ml-client-test.yml/badge.svg)
![Web App Tests](https://github.com/swe-students-spring2026/4-containers-design_ant-4/actions/workflows/webapp-test.yml/badge.svg)

# Fridge Food Detector

A containerized application that uses machine learning to detect food items in fridge photos. Users upload an image of their fridge, and the system automatically identifies food items using [Grounding DINO](https://github.com/IDEA-Research/GroundingDINO) (an open-vocabulary object detection model), then displays the detected inventory on a web dashboard where items can be renamed or deleted.

## Team Members
- [Roger](https://github.com/DaobaRoger12)
- [Zelu Zhang](https://github.com/zzl0720-2025)

## Architecture

The system consists of three containerized subsystems:

| Container | Description |
|-----------|-------------|
| **Web App** | Flask web server. Provides an upload page and an inventory dashboard. Communicates with MongoDB and invokes the ML client. |
| **ML Client** | Python script using Grounding DINO to perform open-vocabulary food detection on uploaded images. Outputs structured JSON results and annotated images. |
| **Database** | MongoDB instance for storing upload metadata and detected inventory items. |

## Prerequisites

- [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/)
- Python 3.10+ (for local development without Docker)
- Git

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/swe-students-spring2026/4-containers-design_ant-4.git
cd 4-containers-design_ant-4
```

### 2. Set up environment variables

Copy the example env file and edit as needed:

```bash
cp env.example web-app/.env
```

The `.env` file should contain:

```
SECRET_KEY=your-secret-key-here
MONGO_URI=mongodb://mongodb:27017/
DB_NAME=fridge_app
```

### 3. Run with Docker Compose

```bash
docker-compose up --build
```

This starts all three containers:
- Web app at [http://localhost:5000](http://localhost:5000)
- MongoDB at `localhost:27017`
- ML client runs on demand when an image is uploaded

### 4. Run locally (without Docker)

#### MongoDB

```bash
docker run --name mongodb -d -p 27017:27017 mongo
```

#### Web App

```bash
cd web-app
python -m pip install -r requirements.txt
cp ../.env.example .env   # edit if needed
python app.py
```

The web app will be available at [http://localhost:5000](http://localhost:5000).

#### ML Client

```bash
cd machine-learning-client
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The ML client is invoked automatically by the web app when an image is uploaded. To run it standalone:

```bash
python food_detection.py --input ./test_images --output ./results
```

## Usage

1. Open [http://localhost:5000](http://localhost:5000) in your browser.
2. Upload a photo of your fridge.
3. The ML model detects food items and saves results to the database.
4. View detected items on the [Inventory Dashboard](http://localhost:5000/dashboard).
5. Edit item names or delete items from the dashboard.

## Running Tests

### Web App

```bash
cd web-app
pip install -r requirements.txt
pytest
```

### ML Client

```bash
cd machine-learning-client
pip install -r requirements.txt
pip install pytest pytest-cov
pytest --cov=food_detection --cov-fail-under=80
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-secret-key` | Flask secret key for session management |
| `MONGO_URI` | `mongodb://localhost:27017/` | MongoDB connection string |
| `MONGO_DB_NAME` | `fridge_app` | MongoDB database name |

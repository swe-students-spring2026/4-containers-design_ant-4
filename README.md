![Lint](https://github.com/swe-students-spring2026/4-containers-design_ant-4/actions/workflows/lint.yml/badge.svg)
![ML Client Tests](https://github.com/swe-students-spring2026/4-containers-design_ant-4/actions/workflows/ml-client-test.yml/badge.svg)
![Web App Tests](https://github.com/swe-students-spring2026/4-containers-design_ant-4/actions/workflows/webapp-test.yml/badge.svg)

# Fridge Food Detector

A containerized application that uses machine learning to detect food items in fridge photos. Users upload an image of their fridge through a Flask web app, the image is sent to a separate ML microservice powered by [Grounding DINO](https://github.com/IDEA-Research/GroundingDINO) for open-vocabulary food detection, and the results are stored in MongoDB and displayed on a per-user inventory dashboard.

## Team Members

- [Roger](https://github.com/DaobaRoger12)
- [Zelu Zhang](https://github.com/zzl0720-2025)
- [William Zhang](https://github.com/Incrediblez7)
- [Mumu Li](https://github.com/zzl0720-2025)

## Architecture

The system consists of three Docker containers:

| Container | Port | Description |
|-----------|------|-------------|
| **Web App** | 5000 | Flask server with user authentication (register/login), image upload, inventory dashboard, and scan queue. Sends uploaded images to the ML client via HTTP. |
| **ML Client** | 10990 | Flask microservice that receives images, runs Grounding DINO food detection, saves results to MongoDB, and calls back to the web app when processing completes. |
| **MongoDB** | 27017 | Stores user accounts, upload records, ML detection results, and inventory items. |

## Prerequisites

- [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/)
- Git

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/swe-students-spring2026/4-containers-design_ant-4.git
cd 4-containers-design_ant-4
```

### 2. Run with Docker Compose

```bash
docker-compose up --build
```

All services use sensible defaults and connect to each other via Docker service names automatically — no configuration files needed.

Once all containers are running:

- Web app: [http://localhost:5000](http://localhost:5000)
- Create an account, then upload a fridge photo to start detecting food items.

### Running locally (without Docker)

If you prefer to run each part outside of Docker, you need to override `MONGO_URI` so the services point at localhost instead of the Docker service name.

**Start MongoDB:**

```bash
docker run --name mongodb -d -p 27017:27017 mongo
```

**Start the ML Client:**

```bash
cd machine-learning-client
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
MONGO_URI=mongodb://localhost:27017/ python ml_client_service.py
```

**Start the Web App** (in a separate terminal):

```bash
cd web-app
pip install -r requirements.txt
MONGO_URI=mongodb://localhost:27017/ flask run --host=0.0.0.0 --port=5000
```

## Usage

1. Open [http://localhost:5000](http://localhost:5000).
2. Register a new account or log in.
3. Upload a photo of your fridge from the home page.
4. Check the **Scan Queue** page to see processing status.
5. Once processing completes, view detected food items on your **Dashboard**.
6. Rename or delete items from the dashboard as needed.

## Running Tests

**Web App:**

```bash
cd web-app
pip install -r requirements.txt
pytest
```

**ML Client:**

```bash
cd machine-learning-client
pip install -r requirements.txt
pip install pytest pytest-cov
pytest --cov=food_detection --cov-fail-under=80
```

# Short.ly by Devesh 
**A High-Performance, Polyglot Microservice URL Shortener**
### VISIT LIVE DEPLOYED WEBSITE AT shls.railway.app
This isn't just a simple link shortener. It is a distributed system designed for high scale, combining the raw speed of **C++**, the flexibility of **Python**, and the low latency of **Redis**.

##  The Architecture
- **The Brain (C++)**: A high-speed microservice using the **Crow** framework for Base62 encoding.
- **The Manager (Python/FastAPI)**: Orchestrates the workflow, validates URLs, and manages the API.
- **The Persistence (PostgreSQL)**: Ensures your links never disappear.
- **The Speed Layer (Redis)**: Serves popular links from RAM in **<1ms** and tracks real-time click analytics.
- **The Box (Docker)**: One-click deployment for the entire 4-service cluster.

##  Performance (Locust Load Test)
In stress tests, this system handled **800+ requests per second** for redirects with **0% failure rate**, proving the efficiency of the Redis caching layer.

##  Business Analytics
- Real-time click tracking by **State** and **Country**.
- Device type identification (Mobile vs. Desktop).
- Live dashboard polling via JavaScript.

##  Run it in 30 Seconds
Ensure you have Docker installed, then run:
```bash
docker compose up --build


The dashboard will be live at http://localhost:8000

ARCHITCTURE OF THE SYSTEM FOR KNWOLEDGE PURPOSE ONLY
graph TD
    %% User Layer
    User(( End User)) -->|Paste URL| Frontend[Tailwind Dashboard]
    User -->|Click Link| Frontend

    %% API Layer (The Manager)
    subgraph FastAPI_Container [Python Microservice]
        Frontend -->|POST /shorten| API[ FastAPI Manager]
        Frontend -->|GET /stats| API
        API -->|Check Cache| Redis
    end

    %% Logic Layer (The Brain)
    subgraph CPP_Container [C++ Microservice]
        API -->|HTTP Request| Crow[ Crow Encoder]
        Crow -->|Base62 Logic| ID[Unique ID to Short Code]
    end

    %% Storage Layer (Persistence)
    subgraph Data_Layer [Storage Cluster]
        API -->|Save Link| Postgres[( PostgreSQL)]
        API -->|Cache Link & Incr Clicks| Redis[( Redis RAM)]
    end

    %% Flow of Redirect
    User -->|Short Link| API
    API -->|1. Check Redis| Redis
    Redis -- Cache Hit --> API
    API -- Redirect --> User
    
    style User fill:#f9f,stroke:#333,stroke-width:2px
    style CPP_Container fill:#d1e7dd,stroke:#0f5132
    style FastAPI_Container fill:#fff3cd,stroke:#856404
    style Data_Layer fill:#cfe2ff,stroke:#084298

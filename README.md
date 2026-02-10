# BIAT Test Manager

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/django-5.x-green.svg)
![React](https://img.shields.io/badge/react-18.x-blue.svg)

An intelligent test management and automation platform that leverages artificial intelligence to revolutionize the software quality assurance lifecycle in banking environments.

## 🎯 Project Overview

BIAT Test Manager is an AI-powered testing platform inspired by industry leaders like Focus & Thunders. It combines comprehensive test management with AI-driven test generation and live execution capabilities, enabling human-AI collaboration in software testing.

## 🚀 Key Features

### 1. **Core Platform**
- Project and test management structures
- User authentication and role-based access control
- Core data models: Requirements, Test Suites, Scenarios, Test Cases, Execution Sessions
- Complete traceability from requirements to test results

### 2. **Requirement Ingestion & AI Test Generation**
- Multi-source requirement ingestion:
  - CSV, Excel... file uploads
  - Jira issue synchronization
  - Unified requirement normalization
- AI-powered test generation using Claude MCP:
  - Automatic test suite generation
  - Intelligent test scenario creation
  - Advanced coverage analysis
- Human review and approval workflow
- Full requirement-to-test traceability

### 3. **Execution Engine & Real-time Streaming**
- Automated test execution with Playwright
- Parallel test execution support
- Real-time streaming of:
  - Execution states (running, passed, failed)
  - Live logs
  - Screenshots and videos
- Reliable results storage and history

### 4. **Live Control & Human Intervention** ⭐
- **KaneAI-style human intervention**:
  - Pause/Resume/Stop execution controls
  - Manual browser takeover during execution
  - State preservation and resume capability
- Handle unexpected UI behavior
- Stabilization and error recovery
- Human-AI collaborative testing

### 5. **Test Results Dashboard & CI/CD Integration**
- Comprehensive results dashboard:
  - Pass/fail metrics
  - Execution time analytics
  - Log viewer
  - Screenshot gallery
- Jenkins CI/CD pipeline integration
- Export runnable Playwright/Selenium test artifacts

## 🏗️ Architecture

### Tech Stack

**Backend:**
- Django 5.x + Django REST Framework
- Django Channels (WebSockets)
- PostgreSQL (Database)
- Redis (Caching & Message Broker)
- Celery (Async Task Queue)

**Frontend:**
- React 18 + Vite
- Tailwind CSS + shadcn/ui
- Socket.io-client (Real-time updates)
- Recharts (Analytics)

**AI/Automation:**
- Anthropic Claude API (MCP-based test generation)
- LangChain (LLM orchestration)
- Playwright (Browser automation)

**DevOps:**
- Docker + Docker Compose
- Jenkins (CI/CD)
- GitHub Actions

## 📊 Use Case Diagram

\`\`\`mermaid
graph TB
    subgraph Actors
        Admin[Administrator]
        Tester[Tester]
        Viewer[Viewer]
        AI[AI Agent]
    end
    
    subgraph "BIAT Test Manager System"
        subgraph "User Management"
            UC1[Manage Users & Roles]
            UC2[Authenticate & Authorize]
        end
        
        subgraph "Requirement Management"
            UC3[Upload Requirements Files]
            UC4[Sync Jira Issues]
            UC5[Normalize Requirements]
            UC6[View Requirement Traceability]
        end
        
        subgraph "Test Generation"
            UC7[Generate Test Suites AI]
            UC8[Generate Test Scenarios AI]
            UC9[Generate Test Cases AI]
            UC10[Review & Approve Tests]
            UC11[Edit Generated Tests]
        end
        
        subgraph "Test Execution"
            UC12[Execute Tests Automated]
            UC13[Execute Tests in Parallel]
            UC14[Stream Execution Live]
            UC15[Pause/Resume Execution]
            UC16[Take Manual Control]
            UC17[Stop Execution]
        end
        
        subgraph "Results & Reporting"
            UC18[View Test Results]
            UC19[View Execution Logs]
            UC20[View Screenshots/Videos]
            UC21[Generate Reports]
            UC22[Export to CI/CD]
        end
    end
    
    Admin --> UC1
    Admin --> UC2
    Tester --> UC2
    Viewer --> UC2
    
    Tester --> UC3
    Tester --> UC4
    UC3 --> UC5
    UC4 --> UC5
    Tester --> UC6
    Viewer --> UC6
    
    Tester --> UC7
    AI --> UC7
    AI --> UC8
    AI --> UC9
    Tester --> UC10
    Tester --> UC11
    
    Tester --> UC12
    UC12 --> UC13
    UC12 --> UC14
    Tester --> UC15
    Tester --> UC16
    Tester --> UC17
    
    Tester --> UC18
    Viewer --> UC18
    Tester --> UC19
    Viewer --> UC19
    Tester --> UC20
    Viewer --> UC20
    Admin --> UC21
    Tester --> UC21
    Admin --> UC22
\`\`\`

## 🗂️ Class Diagram

\`\`\`mermaid
classDiagram
    class User {
        +int id
        +string username
        +string email
        +string password_hash
        +string role
        +datetime created_at
        +login()
        +logout()
        +hasPermission(permission)
    }
    
    class Project {
        +int id
        +string name
        +string description
        +User owner
        +datetime created_at
        +datetime updated_at
        +addMember(user, role)
        +removeMember(user)
    }
    
    class Requirement {
        +int id
        +string source_type
        +string source_id
        +string title
        +string description
        +string priority
        +json metadata
        +Project project
        +datetime created_at
        +normalize()
        +linkToJira()
    }
    
    class TestSuite {
        +int id
        +string name
        +string description
        +Requirement requirement
        +Project project
        +User created_by
        +datetime created_at
        +boolean ai_generated
        +addScenario(scenario)
        +removeScenario(scenario)
    }
    
    class TestScenario {
        +int id
        +string name
        +string description
        +TestSuite suite
        +int priority
        +boolean ai_generated
        +datetime created_at
        +addTestCase(testCase)
        +calculateCoverage()
    }
    
    class TestCase {
        +int id
        +string name
        +string description
        +TestScenario scenario
        +json steps
        +json expected_results
        +string status
        +User approved_by
        +datetime approved_at
        +boolean ai_generated
        +approve(user)
        +reject(user)
        +edit(steps, expectedResults)
        +generateScript()
    }
    
    class ExecutionSession {
        +int id
        +string session_id
        +Project project
        +User started_by
        +datetime started_at
        +datetime ended_at
        +string status
        +json configuration
        +startExecution()
        +pauseExecution()
        +resumeExecution()
        +stopExecution()
        +getResults()
    }
    
    class TestExecution {
        +int id
        +TestCase test_case
        +ExecutionSession session
        +string status
        +datetime started_at
        +datetime ended_at
        +int duration_ms
        +string error_message
        +boolean manual_intervention
        +User intervened_by
        +execute()
        +pause()
        +resume()
        +takeManualControl()
        +releaseControl()
    }
    
    class ExecutionLog {
        +int id
        +TestExecution execution
        +string level
        +string message
        +json metadata
        +datetime timestamp
        +log(level, message)
    }
    
    class Screenshot {
        +int id
        +TestExecution execution
        +string file_path
        +string storage_url
        +datetime captured_at
        +capture()
        +delete()
    }
    
    class AITestGenerator {
        +string model_name
        +json configuration
        +generateTestSuite(requirement)
        +generateScenarios(testSuite)
        +generateTestCases(scenario)
        +analyzeRequirement(requirement)
        +suggestCoverage(requirement)
    }
    
    class PlaywrightExecutor {
        +string browser_type
        +json configuration
        +executeTestCase(testCase)
        +captureScreenshot()
        +captureLogs()
        +handleError(error)
        +pause()
        +resume()
        +handoverControl(user)
    }
    
    class WebSocketStreamer {
        +string channel_name
        +broadcast(event, data)
        +sendExecutionUpdate(execution)
        +sendLogUpdate(log)
        +sendScreenshot(screenshot)
    }
    
    User "1" --> "*" Project : owns
    Project "1" --> "*" Requirement : contains
    Project "1" --> "*" TestSuite : contains
    Requirement "1" --> "*" TestSuite : generates
    TestSuite "1" --> "*" TestScenario : contains
    TestScenario "1" --> "*" TestCase : contains
    TestCase "1" --> "*" TestExecution : executed in
    ExecutionSession "1" --> "*" TestExecution : contains
    TestExecution "1" --> "*" ExecutionLog : generates
    TestExecution "1" --> "*" Screenshot : captures
    User "1" --> "*" ExecutionSession : starts
    User "1" --> "*" TestCase : approves
    User "0..1" --> "*" TestExecution : intervenes
    
    AITestGenerator ..> TestSuite : generates
    AITestGenerator ..> TestScenario : generates
    AITestGenerator ..> TestCase : generates
    PlaywrightExecutor ..> TestExecution : executes
    WebSocketStreamer ..> TestExecution : streams
    WebSocketStreamer ..> ExecutionLog : streams
    WebSocketStreamer ..> Screenshot : streams
\`\`\`

## 📦 Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose (optional)

### Backend Setup

\`\`\`bash
# Clone the repository
git clone https://github.com/yourusername/biat-test-manager.git
cd biat-test-manager

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start Redis (if not using Docker)
redis-server

# Start Celery worker
celery -A config worker -l info

# Start Django development server
python manage.py runserver
\`\`\`

### Frontend Setup

\`\`\`bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your API endpoints

# Start development server
npm run dev
\`\`\`

### Docker Setup (Recommended)

\`\`\`bash
# Build and start all services
docker-compose up -d

# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# Admin: http://localhost:8000/admin
\`\`\`

## 🎮 Usage

### 1. Upload Requirements
\`\`\`python
# Upload CSV, Excel, or PDF files
# Or sync from Jira
POST /api/requirements/upload/
POST /api/requirements/jira/sync/
\`\`\`

### 2. Generate Tests with AI
\`\`\`python
# Generate test suite from requirement
POST /api/test-generation/suite/
{
  "requirement_id": 1,
  "coverage_level": "comprehensive"
}
\`\`\`

### 3. Review and Approve Tests
\`\`\`python
# Approve AI-generated test case
PATCH /api/test-cases/{id}/approve/
\`\`\`

### 4. Execute Tests
\`\`\`python
# Start execution session
POST /api/executions/sessions/
{
  "test_case_ids": [1, 2, 3],
  "parallel": true,
  "browser": "chromium"
}
\`\`\`

### 5. Live Control During Execution
\`\`\`javascript
// WebSocket connection for live updates
const socket = io('http://localhost:8000');

socket.on('execution_update', (data) => {
  console.log('Status:', data.status);
  console.log('Screenshot:', data.screenshot_url);
});

// Take manual control
POST /api/executions/{id}/take-control/

// Resume AI execution
POST /api/executions/{id}/resume/
\`\`\`

## 🧪 Testing

\`\`\`bash
# Run backend tests
python manage.py test

# Run frontend tests
npm test

# Run E2E tests
npm run test:e2e

# Run with coverage
pytest --cov=apps --cov-report=html
\`\`\`

## 📚 API Documentation

API documentation is available at:
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Team

- **Project Lead**: [Your Name]
- **Backend Developer**: [Name]
- **Frontend Developer**: [Name]
- **AI/ML Engineer**: [Name]
- **QA Engineer**: [Name]

## 🙏 Acknowledgments

- Inspired by industry leaders: Focus & Thunders
- Built with [Django](https://www.djangoproject.com/)
- Powered by [Anthropic Claude](https://www.anthropic.com/)
- Automated with [Playwright](https://playwright.dev/)

## 📞 Support

For support, email support@biat-test-manager.com or join our Slack channel.

## 🗺️ Roadmap

- [x] Phase 1: Analysis & Architecture
- [x] Phase 2: Core Platform
- [x] Phase 3: Requirement Ingestion
- [ ] Phase 4: AI Test Generation (In Progress)
- [ ] Phase 5: Execution Engine & Streaming
- [ ] Phase 6: Live Control & Human Intervention
- [ ] CI/CD Integration
- [ ] Mobile App Support
- [ ] Advanced Analytics Dashboard

---

**Built with ❤️ for the banking industry**

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
- AI-powered test generation:
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

**Frontend:**
- React 18 + Vite
- Tailwind CSS + shadcn/ui
- Socket.io-client (Real-time updates)

**AI/Automation:**
- MCP servers like Playwright MCP etc...
- LangChain (LLM orchestration) / LangGraph
- Playwright (Browser automation)

## 📚 API Documentation

API documentation is available at:
- Swagger UI: `http://localhost:8000/api/docs/`

## 👥 Team

- **Project Lead**: Wael Abid
- **ML Engineer**: Aziz Allah Barkaoui 
- **QA Engineer**: Baccar Mihed


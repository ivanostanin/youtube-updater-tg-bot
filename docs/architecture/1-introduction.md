# 1. Introduction

## 1.1 Document Purpose

This document outlines the architectural approach for enhancing YouTube Updater Telegram Bot with advanced features including admin access control, premium AI-powered summaries, auto-deletion timers, and update history management. Its primary goal is to serve as the guiding architectural blueprint for AI-driven development of new features while ensuring seamless integration with the existing system.

This document supplements existing project architecture by defining how new components will integrate with current systems. Where conflicts arise between new and existing patterns, this document provides guidance on maintaining consistency while implementing enhancements.

## 1.2 Existing Project Analysis

**Current Project State:**

- **Primary Purpose:** Telegram bot providing real-time YouTube channel update notifications via PubSubHubbub webhooks
- **Current Tech Stack:** Python 3.13, python-telegram-bot 22.5, Starlette 0.48, SQLAlchemy 2.0 (async), SQLite/aiosqlite, httpx, Pydantic 2.11
- **Architecture Style:** Dual-threaded async application (Telegram polling in main thread + Starlette webhook server in daemon thread), Repository pattern for data access, event-driven webhook notifications
- **Deployment Method:** Docker containerization with Kubernetes Helm chart, GitHub Actions CI/CD, OCI Kubernetes cluster target

## 1.3 Available Documentation

- **Project Brief:** `docs/brief.md` - Complete project vision, user stories, MVP scope, and technical considerations
- **Sharded PRD:** `docs/prd/` directory with introduction, requirements, technical constraints, and epic/story structure
- **CLAUDE.md:** Developer guidance for Claude Code with common commands, architecture notes, and development workflow
- **README.md:** Quick start guide, bot commands, and basic architecture overview
- **Helm Chart:** `deployment/helm/youtube-updater-tg-bot/` with values, templates, and deployment configuration

## 1.4 Identified Constraints

- **Threading Model:** Bot polling runs in main thread; webhook server runs in separate daemon thread with 1-second startup delay
- **Hardcoded Webhook URL:** Currently set to `https://youtube-bot.nmro.cc/webhook/youtube` in `handlers.py:19`
- **No Database Migrations:** Schema created via `Base.metadata.create_all()` without migration framework (Alembic not integrated)
- **Admin ACL Not Implemented:** PRD specifies admin verification for groups/channels, but code only checks subscriptions without role verification
- **SQLite Scaling Concerns:** Current SQLite setup may struggle with concurrent writes; PostgreSQL migration path mentioned but not implemented
- **Limited Test Coverage:** pytest configured but no existing test files in repository
- **Notification Service Minimal:** Basic message sending without formatting customization, thumbnails, or rich media support
- **No Background Job Scheduler:** Webhook renewal and cleanup tasks mentioned in PRD but not implemented

## 1.5 Change Log

| Change               | Date       | Version | Description                                                                | Author              |
|----------------------|------------|---------|----------------------------------------------------------------------------|---------------------|
| Initial Architecture | 2025-11-01 | 1.0     | Brownfield architecture document created based on existing v0.1.0 codebase | Winston (Architect) |

---

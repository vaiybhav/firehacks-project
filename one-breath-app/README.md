# Horizons App

A meditation and yoga app built with React, TypeScript, and Vite.

**🌐 Production: [horizons.socials](https://horizons.socials)** (when deployed)

## Quick Start - Localhost

### Start Development Server

```bash
cd one-breath-app
./start.sh
```

Or manually:

```bash
cd one-breath-app
npm install  # Only needed first time
npm run dev
```

Then open in your browser: **http://localhost:8080**

The app will automatically reload when you make changes.

### Production Build

```bash
cd one-breath-app
npm run build
```

This creates a `dist/` folder ready for deployment.

## Deployment

See [DEPLOY.md](./DEPLOY.md) for detailed deployment instructions.

**Quick Deploy to Vercel:**
```bash
npm i -g vercel
cd one-breath-app
vercel
vercel domains add horizons.socials
```

## Features

- 🌬️ Meditation practices
- 🧘 Yoga sessions with personalized plans
- 📊 Progress tracking
- 👥 Community features
- ✨ Onboarding flow with health/age/weight input
- 🎯 Personalized yoga plan generation

## Tech Stack

- React 18
- TypeScript
- Vite
- Tailwind CSS
- React Router


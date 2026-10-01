# Atlas Frontend

React-based frontend application for the Atlas platform, built with React Router v7 and Vite.

## Prerequisites

- Node.js 22+
- npm (comes with Node.js)
- A configured Keycloak instance for authentication

## Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
# Keycloak Authentication
VITE_KEYCLOAK_AUTH_URL=https://auth.example.com/realms/your-realm/protocol/openid-connect
VITE_KEYCLOAK_CLIENT_ID=your-client-id

# Frontend URL (for OAuth redirects)
VITE_ATLAS_FRONTEND_URL=http://localhost:5173

# Backend API
VITE_ATLAS_API_URL=http://localhost:3000/api
VITE_ATLAS_API_TOKEN=your-api-token-here
```

### 3. Run Development Server

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run typecheck` - Run TypeScript type checking

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_KEYCLOAK_AUTH_URL` | Full path to Keycloak OpenID Connect endpoint | `https://auth.example.com/realms/your-realm/protocol/openid-connect` |
| `VITE_KEYCLOAK_CLIENT_ID` | Keycloak client ID | `your-client-id` |
| `VITE_ATLAS_FRONTEND_URL` | Frontend URL for OAuth redirects | `http://localhost:5173` |
| `VITE_ATLAS_API_URL` | Backend API base URL | `http://localhost:3000/api` |
| `VITE_ATLAS_API_TOKEN` | API authentication token | `your-token` |

## Tech Stack

- **React** 19.2
- **React Router** 7.9
- **Vite** 7.1
- **TypeScript** 5.9
- **Tailwind CSS** 4.1
- **Framer Motion** - Animations
- **Axios** - HTTP client
- **Lucide React** - Icons

## Authentication

The application uses Keycloak for authentication with OAuth 2.0 PKCE (Proof Key for Code Exchange) flow. Users are redirected to Keycloak for login, and tokens are stored in localStorage.

## Project Structure

```
app/
├── routes/          # Route components
├── components/      # Reusable components
├── types/           # TypeScript type definitions
└── auth.ts          # Authentication logic
```

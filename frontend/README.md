# Cache Quest Frontend

Mobile-first React frontend for the Cache Quest geocaching platform.

## Features

- **Mobile-First Design**: Optimized for outdoor use on phones
  - 44x44px minimum tap targets
  - High contrast for sunlight readability
  - Full-screen map on mobile
  - Bottom sheets instead of modals on mobile
  - Proper mobile keyboard handling

- **Authentication**: Token-based auth with localStorage persistence
- **Interactive Map**: Leaflet.js with custom markers
  - Green pulsing markers for unclaimed caches
  - Grey markers for found caches
  - Visual clue circles
- **Responsive**: Desktop and mobile optimized

## Tech Stack

- React 18
- Vite
- React Router v6
- Leaflet.js
- TailwindCSS
- Axios

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment**:
   - Copy `.env` and adjust if needed (default: `http://localhost:8000`)

3. **Run development server**:
   ```bash
   npm run dev
   ```

4. **Build for production**:
   ```bash
   npm run build
   ```

## Project Structure

```
src/
├── components/
│   ├── BottomSheet.jsx       # Mobile bottom sheet
│   ├── Icons.jsx              # SVG icon components
│   ├── ProtectedRoute.jsx    # Auth route wrapper
│   └── SpotMarker.jsx        # Leaflet marker component
├── context/
│   └── AuthContext.jsx       # Authentication context
├── hooks/
│   └── useWindowSize.jsx     # Responsive hook
├── pages/
│   ├── LoginPage.jsx         # Login form
│   └── MapPage.jsx           # Main map view
├── utils/
│   └── axiosInstance.js      # Configured axios
├── App.jsx                    # Main app with routing
├── main.jsx                   # App entry point
└── index.css                  # Global styles + Tailwind
```

## API Requirements

Backend must provide these endpoints:

- `POST /api/auth/login/` - Login with username/password
- `POST /api/auth/logout/` - Logout
- `GET /api/auth/me/` - Get current user
- `GET /api/spots/` - List all spots (with fuzzy_lat, fuzzy_lng)
- `GET /api/spots/<id>/clue/` - Get clue and fuzzy circle
- `GET /api/users/me/finds/` - Get user's found caches

## Mobile-First Guidelines

All interactive elements follow mobile-first principles:

- **Tap Targets**: Minimum 44x44px for all buttons, links, inputs
- **No Hover-Only**: All interactions work on touch
- **Full-Screen Map**: No sidebars on mobile
- **Bottom Sheets**: Slide-up modals on mobile, centered on desktop
- **High Contrast**: Readable in bright sunlight
- **Keyboard-Aware**: Proper input types and autocomplete

## License

Open source geocaching platform.


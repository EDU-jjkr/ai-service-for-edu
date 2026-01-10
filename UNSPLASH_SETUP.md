# Unsplash API Setup Guide

## API Keys Explained

Unsplash provides different credentials for different use cases:

### What We Need ✅
**Access Key (Client ID)** - For server-side public API access
- Used to search and download photos
- This is all we need for the Chalkie system
- Free tier: 50 requests/hour

### What We Don't Need ❌
**Secret Key** - Only for OAuth user authentication
- Used when users need to login to Unsplash through your app
- We're not implementing user login, so we don't need this

**Redirect URI** - Only for OAuth flows
- URL where Unsplash redirects after user authorization
- Not needed for our server-side API access

---

## Setup Instructions

1. **Go to Unsplash Developers Portal**
   - Visit: https://unsplash.com/developers
   - Sign in or create an account

2. **Create a New Application**
   - Click "New Application"
   - Accept the API Use and Guidelines
   - Give your app a name (e.g., "Chalkie Deck Generator")
   - Description: "Educational PowerPoint generation system"

3. **Get Your Access Key**
   - After creating the app, you'll see your **Access Key**
   - Copy this key (it looks like: `abc123def456...`)

4. **Add to .env File**
   ```bash
   UNSPLASH_API_KEY=your_access_key_here
   ```

5. **Test the Connection**
   ```bash
   curl -H "Authorization: Client-ID YOUR_ACCESS_KEY" \
   "https://api.unsplash.com/search/photos?query=ocean&per_page=1"
   ```

---

## Pexels Setup (Fallback API)

1. **Go to Pexels API**
   - Visit: https://www.pexels.com/api/
   
2. **Request API Access**
   - Sign up with your email
   - You'll receive an API key immediately

3. **Add to .env File**
   ```bash
   PEXELS_API_KEY=your_pexels_key_here
   ```

---

## Important Notes

- ✅ **Access Key** is safe to use server-side
- ❌ **Never expose keys in client-side code** (frontend)
- 🔄 **Fallback strategy**: Unsplash → Pexels → None
- 📊 **Free tier limits**:
  - Unsplash: 50 requests/hour
  - Pexels: 200 requests/hour
- 📸 **Attribution**: Both APIs require photographer credits (we handle this automatically)

---

## What Goes in .env

```bash
# Only these two keys are needed:
UNSPLASH_API_KEY=abc123def456...
PEXELS_API_KEY=xyz789ghi012...

# You do NOT need:
# UNSPLASH_SECRET_KEY (not required)
# UNSPLASH_REDIRECT_URI (not required)
```

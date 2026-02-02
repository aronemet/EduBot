# EduBot Deployment Guide

## 🚀 Deploy to Railway (Recommended)

### Step 1: Prepare for GitHub
1. Create a new repository on GitHub
2. Upload all files to the repository
3. Make sure `.env` is NOT uploaded (it's in .gitignore)

### Step 2: Deploy to Railway
1. Go to [Railway.app](https://railway.app)
2. Sign up/Login with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your EduBot repository
5. Railway will automatically detect it's a Python app

### Step 3: Set Environment Variables
In Railway dashboard, go to your project → Variables tab and add:

```
LLAMA_API_KEY=your_openrouter_api_key_here
GEMMA_API_KEY=your_openrouter_api_key_here  
ADMIN_KEY=your_secret_admin_key_here
```

### Step 4: Access Your App
- Railway will give you a URL like: `https://your-app-name.railway.app`
- Users can access EduBot at this URL
- You can access feedback at: `https://your-app-name.railway.app/admin/feedback?admin_key=your_secret_admin_key_here`

## 📊 Viewing Feedback & Bug Reports

### Method 1: Railway Logs (Recommended)
1. Go to Railway dashboard → Your project
2. Click on "Deployments" tab
3. Click on the latest deployment
4. View logs and search for:
   - `FEEDBACK_SUBMISSION:` for user feedback
   - `BUG_REPORT_SUBMISSION:` for bug reports

### Method 2: Admin Endpoint
Visit: `https://your-app-name.railway.app/admin/feedback?admin_key=YOUR_ADMIN_KEY`

## 🔒 Security Notes

- **NEVER** share your ADMIN_KEY publicly
- **NEVER** commit your `.env` file to GitHub
- Change your ADMIN_KEY regularly
- Only you can access the feedback with the admin key

## 📁 File Structure for GitHub
```
edubot/
├── backend/
│   └── main.py
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── styles.css
├── requirements.txt
├── Procfile
├── railway.json
├── .env.example
├── .gitignore
└── README.md
```

## 🌐 How Users Will Access
- Users visit your Railway URL
- They can use EduBot normally
- When they submit feedback/bugs, it goes to your logs
- Only you can see the feedback with your admin key

## 💡 Tips
- Test locally first: `cd backend && python main.py`
- Check Railway logs regularly for feedback
- Keep your API keys secure
- Monitor usage through Railway dashboard
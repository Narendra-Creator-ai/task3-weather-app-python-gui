# GitHub Repo Publish Steps

## 1. Add your screenshot
1. Save your weather app output screenshot as:
   - `docs/task3-output.png`
2. Keep this exact filename so the README image renders.

## 2. Initialize local repo in this folder
```cmd
cd "C:\My Stuff\my projects\Sqrock TASKS\Task- 3"
git init
git branch -M main
git add .
git commit -m "feat: build API-based weather GUI app with forecast and persistence"
```

## 3. Create GitHub repository
1. Open [https://github.com/new](https://github.com/new)
2. Repository name suggestion:
   - `task3-weather-app-python`
3. Keep it Public (recommended for portfolio)
4. Click **Create repository**

## 4. Connect and push
Replace `YOUR_USERNAME` with your GitHub username:

```cmd
git remote add origin https://github.com/YOUR_USERNAME/task3-weather-app-python.git
git push -u origin main
```

## Suggested repo description
Python Tkinter weather app using OpenWeather API with live data, 5-day forecast, saved cities, and API key persistence.

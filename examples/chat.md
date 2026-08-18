<!-- humanizer:allow: the Before block quotes bad writing on purpose -->

# Example: always-on chat voice

User rule (Claude Code, Cursor, or any harness with standing rules):

```
Use the unslopify skill in every reply. Always-on mode.
```

## Before (default assistant voice)

```text
Great question! Deploying a Next.js app to production involves several
key considerations. Below is a comprehensive overview tailored to your
needs. First and foremost, it's crucial to leverage a robust hosting
platform... In conclusion, following these best practices will ensure
a seamless deployment experience. Let me know if you'd like me to
elaborate on any of these steps!
```

## After (always-on)

```text
Use Vercel. Your app already uses their image loader, and the free
tier covers your traffic. Connect the GitHub repo, set the two env
vars from .env.example, and push. First deploy takes about a minute.
The one thing that will bite you: your cron route needs the Vercel
schedule config, since setInterval dies with the lambda.
```

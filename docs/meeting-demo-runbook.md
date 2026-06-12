# One-Minute Meeting Demo

The meeting visuals are deterministic while the connected ElevenLabs live agent remains the interactive voice.
Director scene controls prompt that same interruptible live agent to explain each visible workspace in Hindi.

## Before The Meeting

1. Open Snapkey and sign in.
2. Click **Talk live**.
3. Press `Ctrl + Shift + D` to briefly confirm the private Demo Director panel exists, then hide it.
4. Confirm the ElevenLabs agent uses a Hindi-capable Indian voice and browser sound is enabled.
5. Configure `MONITORING_CAMERA_URLS` if real prerecorded camera videos should replace the animated fallbacks.
6. Set a strong `DEMO_OPERATOR_SECRET` in Railway.

## Remote Director

On the owner's computer, open:

`https://YOUR-APP.up.railway.app/presenter?demo_session=meeting1`

On your computer, open:

`https://YOUR-APP.up.railway.app/director`

Enter `meeting1` and the exact `DEMO_OPERATOR_SECRET`, then click **Connect**. The status must show
**1 presenter online** before the meeting. Every director button changes the owner's screen and prompts
the connected ElevenLabs live agent to explain that scene in Hindi.

## Add Camera Videos

Upload three short, looping MP4 videos to Cloudinary as video assets. Use public HTTPS delivery URLs ending
in `.mp4`, then set this Railway variable:

`MONITORING_CAMERA_URLS=https://.../cam1.mp4,https://.../cam2.mp4,https://.../cam3.mp4`

For the employee screen-sharing demo, optionally set:

`MONITORING_SCREEN_URL=https://.../screen-demo.mp4`

Keep each clip muted, 720p, and preferably below 20 MB for quick meeting playback. Redeploy Railway after
changing the variables.

## Recommended Showcase

Click **Start conversation**. Snapkey immediately greets Mr. Biswajit.

Use these invisible keyboard controls while the audience sees only the live workspace:

| Shortcut | Scene |
| --- | --- |
| `Ctrl + Alt + 1` | Introduction |
| `Ctrl + Alt + 2` | Yesterday sales |
| `Ctrl + Alt + 3` | Today's calendar and Prayag meeting |
| `Ctrl + Alt + 4` | Office camera 1 |
| `Ctrl + Alt + 5` | Office camera 2 |
| `Ctrl + Alt + 6` | Thank-you screen |

Press `Ctrl + Shift + D` to show or hide the director panel. Its **Auto sequence** button runs all six scenes.

## Suggested Owner Prompts

1. "Introduce yourself."
2. "Show me yesterday's sales."
3. "What is on my calendar today?"
4. "Open office camera one."
5. "Now show camera two."
6. "Thank you."

Trigger the matching scene immediately after each prompt. The visual opens deterministically and the connected
live agent receives a concise Hindi instruction to explain it naturally.

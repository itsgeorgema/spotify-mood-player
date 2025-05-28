# Spotify Mood Player

Select your current mood, and Spotify will play music based on that mood.

Deployed at https://spotify-mood-player.vercel.app/

**IMPORTANT: Because this web app is a personal project and not deployed for commercial use, it is ineligible for Spotify's Extended Quota mode and is therefore in Development mode. As such, you can only authenticate and use the website properly if you are manually configured as a user. 

Additionally, due to recently implemented restrictions on Spotify for developers, I couldn't directly utilize Spotify's provided audio features, nor could I access 30-second previews, so I had to implement a script to download 30-second previews of songs for tracks from a user's Spotify library using iTunes Search API, then analyze the audio to extract my own features with Librosa**

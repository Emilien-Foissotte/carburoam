# Carburoam

Community Available Dashboard to pick and follow your nearest stations,
and get oil from cheapest stations !

[![Watch the video](medias/videocover.png)](https://www.youtube.com/embed/Hdzx-nRAvdI)

Follow along the building of this dashboard [here](https://emilien-foissotte.github.io/posts/posts/2024/05/streamlit-gas-stations/?utm_campaign=GasWebApp)

See the deployed version of the app here [carburoam.streamlit.app](https://carburoam.streamlit.app/)

## Developer Track Notes

Have look under the process I followed to deploy this app under here (might be a too direct), here or on my blog

# ENV management

- GMAIL_APP_PASSWORD : app password for streamlit gmail account
- LOAD_MODE="remote|local" : If remote, need AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
- BUCKET_NAME_STORE: Uri of the bucket where config file is stored, if using remote load mode

# TODO

- [x] Create a profile with password to hide your stations
- [x] Create a validation token by email to reset password (linked to GMail for sending mail)
- [x] Create a profile page to edit email, name, preferred gas types, reset password
- [x] Create an Admin dashboard to query DB, reset password for a user if requested, download the credential file,
      flush verification codes expired, download sqlite DB file (no password hashs stored in here, solely preferences and mail/usernames)
- [x] Create a station page to manage stations, edit them, delete them.
- [x] Add stations from a map, with possibility to geolocate yourself. Switch color and tooltip if station followed or not
- [x] Create the thread for ETL, with monitoring as a background task
- [ ] Add to kill process by admin
- [x] Bootstrap the Database (create gastypes if not exists)
- [x] Create a local and distant mode for `config.yaml` file, distant is on S3.
- [ ] Load the first YAML with admin params as a env variable, not a file on VCS, to bootstrap dashboard distant

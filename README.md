# Gas Stations Dashboard V2

Community Available Dashboard to pick and follow your nearest stations,
and get oil from cheapest stations !

# ENV management

- GMAIL_APP_PASSWORD : app password for streamlit gmail account

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
- [ ] Bootstrap the Database (create gastypes if not exists)
- [ ] Create a local and distant mode for `config.yaml` file, distant is on S3.
- [ ] Load the first YAML with admin params as a env variable, not a file on VCS, to bootstrap dashboard distant

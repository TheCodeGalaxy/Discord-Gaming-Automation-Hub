# n8n Credentials

n8n encrypts and stores credentials (Discord webhooks, Google Calendar, etc.) in its database. Exported credentials can be stored here as `.json` files.

## Security Warning

Do NOT commit unencrypted credentials. n8n encrypts exported credentials using your instance's encryption key. These files are safe to commit but useless without the corresponding n8n instance.

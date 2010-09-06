
# These are the settings that tend to differ between installations of Streamer. Tweak these for your installation.

APP_NAME = "streamer-ade"

# This is the token that will act as a shared secret to verify that this application is the one that registered the given subscription. The hub will send us a challenge containing this token.
SECRET_TOKEN = "SOME_SECRET_TOKEN"

# Should we ignore the hubs defined in the feeds we're consuming
ALWAYS_USE_DEFAULT_HUB = False

# What PSHB hub should we use for feeds that don't support PSHB. pollinghub.appspot.com is a hub I've set up that does polling.
DEFAULT_HUB = "http://pollinghub.appspot.com/"

# Should anyone be able to add/delete subscriptions or should access be restricted to admins
OPEN_ACCESS = False

# How often should a task, such as registering a subscription, be retried before we give up
MAX_TASK_RETRIES = 10

# Maximum number of items to be fetched for any part of the system that wants everything of a given data model type
MAX_FETCH = 500

# Should Streamer check that posts it receives from a putative hub are for feeds it's actually subscribed to
SHOULD_VERIFY_INCOMING_POSTS = False
# Installation specific config ends.
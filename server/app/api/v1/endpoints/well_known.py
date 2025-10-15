from fastapi import APIRouter
from starlette.responses import JSONResponse

router = APIRouter()

""" NOT RELEVANT RIGHT NOW AS THE FILE IS SERVED VIA NGINX"""
""" NOT RELEVANT RIGHT NOW AS THE FILE IS SERVED VIA NGINX"""

@router.get(
    "/.well-known/assetlinks.json",
    # It's good practice to explicitly define the response class
    # to ensure the correct Content-Type header is sent.
    response_class=JSONResponse
)
async def get_assetlinks():
    """
    Serves the Digital Asset Links file for Android App Links verification.
    """
    asset_links_content = [
  {
    "relation": [
      "delegate_permission/common.handle_all_urls",
      "delegate_permission/common.get_login_creds"
    ],
    "target": {
      "namespace": "android_app",
      "package_name": "info.sebastianorth.effortless",
      "sha256_cert_fingerprints": [
        "76:63:09:46:E0:14:F2:74:26:12:25:C8:F8:D3:BE:9F:16:EE:CF:EA:29:09:04:14:07:42:7A:0D:71:A8:DB:7A",
        "29:3A:1A:33:75:DC:7E:AE:F6:13:86:08:2C:76:07:12:F9:CF:DA:84:2A:22:04:95:EA:4C:D9:0D:A9:F4:ED:11"
      ]
    },
    "include": [
      {
        "path": "/deeplink/*"
      }
    ]
  }
]
    return asset_links_content



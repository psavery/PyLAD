# This script is used to automatically generate error strings from the
# error macros in Acq.h.
# It was used to generate pyxisl/resources/xisl_errors.json

import json

errors = {
    0: 'HIS_ALL_OK',
}
with open('Acq.h', 'r') as rf:
    for line in rf:
        line = line.strip()

        if line.startswith('#define HIS_ERROR_'):
            _, name, value = line.split()
            errors[int(value)] = name

# These are some extras from the demo file
errors = {
    **errors,
    10000: 'WPE_ILLEGAL_BUFFER (10000)',
    10001: 'WPE_ERR_JSON_PARSE (10001)',
    10002: 'WPE_ERR_JSON_UNPACK (10002)',
    10003: 'WPE_ERR_SERVER_ERROR (10003)',
    10004: 'WPE_ERR_CURL_ERROR (10004)',
    10005: 'WPE_ERR_NO_NET_ADAPTER (10005)',
    10006: 'WPE_ERR_ILLEGAL_PARAM (10006)',
    10007: 'WPE_ERR_BASE64_ENCODE (10007)',
    10008: 'WPE_ERR_FORCE_IP (10008)',
    10009: 'WPE_ERR_NET_ADAPTER (10009)',
    10010: 'WPE_ERR_JSON_CREATE (10010)',
    10011: 'WPE_ERR_PROPSTORE (10011)',
}

with open('xisl_errors.json', 'w') as wf:
    json.dump(errors, wf, indent=4)

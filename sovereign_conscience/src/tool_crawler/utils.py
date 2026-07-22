def remove_null_bytes(s, field_name=None, logger=None):
    if isinstance(s, str):
        if '\x00' in s or '\u0000' in s or chr(0) in s:
            msg = f"[DATA_HYGIENE] NUL byte detected and removed from field '{field_name or '?'}'"
            if logger:
                logger.warning(msg)
            else:
                print(msg)
        return s.replace('\x00', '').replace('\u0000', '').replace(chr(0), '')
    return s 
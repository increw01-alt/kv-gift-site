"""Stable hold codes. Human-readable issue text is never a classifier."""
TOPIC_DUPLICATE = 'topic_duplicate'
BODY_DUPLICATE = 'body_duplicate'
IMAGE_READABILITY = 'image_readability'
OTHER = 'other'
HOLD_REASONS = (TOPIC_DUPLICATE, BODY_DUPLICATE, IMAGE_READABILITY, OTHER)
NOVELTY_HOLDS = (TOPIC_DUPLICATE, BODY_DUPLICATE)


def review_hold_reason(review):
    """A body duplicate takes precedence if both body and banner fail."""
    if 'holdReason' in review:
        code = review['holdReason']
        return code if code in HOLD_REASONS else OTHER
    checks = review.get('checks') or {}
    if checks.get('not_duplicate') is False:
        return BODY_DUPLICATE
    if checks.get('image_readable') is False:
        return IMAGE_READABILITY
    return OTHER

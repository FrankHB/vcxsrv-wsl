/*
 * Implementation of HMAC (RFC 2104) for PuTTY, in a general form that
 * can wrap any underlying hash function.
 */

#include "ssh.h"

struct hmac {
    ssh_hash *h_outer, *h_inner, *h_live;
    uint8_t *digest;
    strbuf *text_name;
    ssh2_mac mac;
};

struct hmac_extra {
    const ssh_hashalg *hashalg;
    size_t blklen;
    const char *suffix;
};

static ssh2_mac *hmac_new(const ssh2_macalg *alg, ssh_cipher *cipher)
{
    struct hmac *ctx = snew(struct hmac);
    const struct hmac_extra *extra = (const struct hmac_extra *)alg->extra;

    ctx->h_outer = ctx->h_inner = ctx->h_live = NULL;
    ctx->digest = snewn(extra->hashalg->hlen, uint8_t);

    ctx->text_name = strbuf_new();
    strbuf_catf(ctx->text_name, "HMAC-%s%s",
                extra->hashalg->text_name, extra->suffix);

    ctx->mac.vt = alg;
    BinarySink_DELEGATE_CLEAR(&ctx->mac);

    return &ctx->mac;
}

static void hmac_free(ssh2_mac *mac)
{
    struct hmac *ctx = container_of(mac, struct hmac, mac);
    const struct hmac_extra *extra = (const struct hmac_extra *)mac->vt->extra;

    if (ctx->h_outer)
        ssh_hash_free(ctx->h_outer);
    if (ctx->h_inner)
        ssh_hash_free(ctx->h_inner);
    if (ctx->h_live)
        ssh_hash_free(ctx->h_live);
    smemclr(ctx->digest, extra->hashalg->hlen);
    sfree(ctx->digest);
    strbuf_free(ctx->text_name);

    smemclr(ctx, sizeof(*ctx));
    sfree(ctx);
}

#define PAD_OUTER 0x5C
#define PAD_INNER 0x36

static void hmac_key(ssh2_mac *mac, ptrlen key)
{
    struct hmac *ctx = container_of(mac, struct hmac, mac);
    const struct hmac_extra *extra = (const struct hmac_extra *)mac->vt->extra;

    const uint8_t *kp;
    size_t klen;
    strbuf *sb = NULL;

    if (key.len > extra->blklen) {
        /*
         * RFC 2104 section 2: if the key exceeds the block length of
         * the underlying hash, then we start by hashing the key, and
         * use that hash as the 'true' key for the HMAC construction.
         */
        sb = strbuf_new();
        strbuf_append(sb, extra->hashalg->hlen);

        ssh_hash *htmp = ssh_hash_new(extra->hashalg);
        put_datapl(htmp, key);
        ssh_hash_final(htmp, sb->u);

        kp = sb->u;
        klen = sb->len;
    } else {
        /*
         * A short enough key is used as is.
         */
        kp = (const uint8_t *)key.ptr;
        klen = key.len;
    }

    if (ctx->h_outer)
        ssh_hash_free(ctx->h_outer);
    if (ctx->h_inner)
        ssh_hash_free(ctx->h_inner);

    ctx->h_outer = ssh_hash_new(extra->hashalg);
    for (size_t i = 0; i < klen; i++)
        put_byte(ctx->h_outer, PAD_OUTER ^ kp[i]);
    for (size_t i = klen; i < extra->blklen; i++)
        put_byte(ctx->h_outer, PAD_OUTER);

    ctx->h_inner = ssh_hash_new(extra->hashalg);
    for (size_t i = 0; i < klen; i++)
        put_byte(ctx->h_inner, PAD_INNER ^ kp[i]);
    for (size_t i = klen; i < extra->blklen; i++)
        put_byte(ctx->h_inner, PAD_INNER);

    if (sb)
        strbuf_free(sb);
}

static void hmac_start(ssh2_mac *mac)
{
    struct hmac *ctx = container_of(mac, struct hmac, mac);

    assert(ctx->h_outer);
    if (ctx->h_live)
        ssh_hash_free(ctx->h_live);

    ctx->h_live = ssh_hash_copy(ctx->h_inner);
    BinarySink_DELEGATE_INIT(&ctx->mac, ctx->h_live);
}

static void hmac_genresult(ssh2_mac *mac, unsigned char *output)
{
    struct hmac *ctx = container_of(mac, struct hmac, mac);
    const struct hmac_extra *extra = (const struct hmac_extra *)mac->vt->extra;

    assert(ctx->h_live);
    ssh_hash_final(ctx->h_live, ctx->digest);

    ctx->h_live = NULL;
    BinarySink_DELEGATE_CLEAR(&ctx->mac);

    ssh_hash *htmp = ssh_hash_copy(ctx->h_outer);
    put_data(htmp, ctx->digest, extra->hashalg->hlen);
    ssh_hash_final(htmp, ctx->digest);

    /*
     * Some instances of HMAC truncate the output hash, so instead of
     * writing it directly to 'output' we wrote it to our own
     * full-length buffer, and now we copy the required amount.
     */
    memcpy(output, ctx->digest, mac->vt->len);
    smemclr(ctx->digest, extra->hashalg->hlen);
}

static const char *hmac_text_name(ssh2_mac *mac)
{
    struct hmac *ctx = container_of(mac, struct hmac, mac);
    return ctx->text_name->s;
}

const struct hmac_extra ssh_hmac_sha256_extra = { &ssh_sha256, 64, "" };
const ssh2_macalg ssh_hmac_sha256 = {
    hmac_new, hmac_free, hmac_key,
    hmac_start, hmac_genresult, hmac_text_name,
    "hmac-sha2-256", "hmac-sha2-256-etm@openssh.com",
    32, 32, &ssh_hmac_sha256_extra,
};

const struct hmac_extra ssh_hmac_md5_extra = { &ssh_md5, 64, "" };
const ssh2_macalg ssh_hmac_md5 = {
    hmac_new, hmac_free, hmac_key,
    hmac_start, hmac_genresult, hmac_text_name,
    "hmac-md5", "hmac-md5-etm@openssh.com",
    16, 16, &ssh_hmac_md5_extra,
};

const struct hmac_extra ssh_hmac_sha1_extra = { &ssh_sha1, 64, "" };

const ssh2_macalg ssh_hmac_sha1 = {
    hmac_new, hmac_free, hmac_key,
    hmac_start, hmac_genresult, hmac_text_name,
    "hmac-sha1", "hmac-sha1-etm@openssh.com",
    20, 20, &ssh_hmac_sha1_extra,
};

const struct hmac_extra ssh_hmac_sha1_96_extra = { &ssh_sha1, 64, "-96" };

const ssh2_macalg ssh_hmac_sha1_96 = {
    hmac_new, hmac_free, hmac_key,
    hmac_start, hmac_genresult, hmac_text_name,
    "hmac-sha1-96", "hmac-sha1-96-etm@openssh.com",
    12, 20, &ssh_hmac_sha1_96_extra,
};

const struct hmac_extra ssh_hmac_sha1_buggy_extra = {
    &ssh_sha1, 64, " (bug-compatible)"
};

const ssh2_macalg ssh_hmac_sha1_buggy = {
    hmac_new, hmac_free, hmac_key,
    hmac_start, hmac_genresult, hmac_text_name,
    "hmac-sha1", NULL,
    20, 16, &ssh_hmac_sha1_buggy_extra,
};

const struct hmac_extra ssh_hmac_sha1_96_buggy_extra = {
    &ssh_sha1, 64, "-96 (bug-compatible)"
};

const ssh2_macalg ssh_hmac_sha1_96_buggy = {
    hmac_new, hmac_free, hmac_key,
    hmac_start, hmac_genresult, hmac_text_name,
    "hmac-sha1-96", NULL,
    12, 16, &ssh_hmac_sha1_96_buggy_extra,
};

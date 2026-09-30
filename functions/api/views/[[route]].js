/**
 * 게시글 조회수 카운터 (Cloudflare Pages Functions + Workers KV)
 *
 *   GET /api/views/<게시판>/<글번호>   → 조회수 +1 후 {n: 누적증가분} 반환
 *   GET /api/views/<게시판>?ids=1,2,3 → 증가 없이 {counts:{글번호:증가분}} 반환 (목록용)
 *
 * 필요 설정(1회): Cloudflare 대시보드 → Workers & Pages → KV에서 네임스페이스 생성 후,
 * Pages 프로젝트(kv-gift-site) → Settings → Functions → KV namespace bindings에
 * 변수 이름 `VIEWS` 로 바인딩. 바인딩 전에는 {disabled:true}를 반환하며 화면은
 * 크롤 시점의 기본 조회수만 표시한다 (오류 없음).
 */
export async function onRequestGet({ params, env, request }) {
  const json = (obj) =>
    new Response(JSON.stringify(obj), {
      headers: {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
        "cache-control": "no-store",
      },
    });

  const kv = env.VIEWS;
  if (!kv) return json({ disabled: true });

  const parts = params.route || [];
  const bo = parts[0];
  if (!bo || !/^[a-z_]{1,30}$/.test(bo)) return json({ error: "board" });

  // 개별 글: 증가 후 반환
  if (parts.length >= 2) {
    const id = parts[1];
    if (!/^\d{1,8}$/.test(id)) return json({ error: "id" });
    const key = `v:${bo}:${id}`;
    const n = parseInt((await kv.get(key)) || "0", 10) + 1;
    await kv.put(key, String(n));
    return json({ n });
  }

  // 목록: ?ids=1,2,3 (증가 없음, 최대 100개)
  const ids = (new URL(request.url).searchParams.get("ids") || "")
    .split(",")
    .filter((s) => /^\d{1,8}$/.test(s))
    .slice(0, 100);
  const counts = {};
  await Promise.all(
    ids.map(async (id) => {
      counts[id] = parseInt((await kv.get(`v:${bo}:${id}`)) || "0", 10);
    })
  );
  return json({ counts });
}

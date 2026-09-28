/** @type {import('next').NextConfig} */
const nextConfig = {
  /* dev サーバーを動かしたまま検証ビルドしたいとき用。
     NEXT_DIST_DIR=.next-verify npm run build → 出力先が分かれ、.next を壊さない */
  distDir: process.env.NEXT_DIST_DIR || '.next',
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.supabase.co',
        pathname: '/storage/v1/object/public/**',
      },
    ],
  },
};

export default nextConfig;

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",          // Needed for Docker / AWS Amplify
  reactStrictMode: true,
};

module.exports = nextConfig;
FROM node:18-alpine

WORKDIR /app

# Copy package configuration
COPY package.json package-lock.json* ./

# Install dependencies
# Using legacy-peer-deps to avoid conflicts with Framer Motion / React 19
RUN npm install --legacy-peer-deps

# Copy the rest of the frontend source code
COPY . .

# We need NEXT_PUBLIC_API_URL available during the build
# so Next.js can bake it into the client-side code if necessary
ARG NEXT_PUBLIC_API_URL=http://localhost:8005
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build Next.js application
RUN npm run build

# Expose port
EXPOSE 3000

# Start Next.js server
CMD ["npm", "start"]

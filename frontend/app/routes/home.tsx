import type { Route } from "./+types/home";
import { Link, useNavigate } from "react-router-dom";
import { login, isLoggedIn, handleRedirectCallback } from "../auth";
import { useState, useEffect } from "react";

export default function Home() {
  const navigate = useNavigate();
  const [showPopUp, setShowPopUp] = useState(false)

  useEffect(() => {
    (async () => {
      await handleRedirectCallback();
      if (isLoggedIn()) {
        navigate("/app/dashboard");
      }
    })();
  }, [navigate]);

  const handleClick = () => { 
    setShowPopUp(true)
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-br from-red-500 via-red-400 to-pink-500">
      <section className="relative z-10 grid min-h-screen place-items-center px-6">
        <div className="text-center max-w-4xl">
          <h1 className="font-extrabold tracking-tight text-white text-4xl sm:text-6xl md:text-7xl">
            <span className="block">Welcome to</span>
            <span className="block mt-2 text-red-600 drop-shadow">
              Atlas
            </span>
          </h1>

          <p className="mt-4 text-base sm:text-lg text-white/80">
            An internal startup-portfolio dashboarding tool
          </p>

          <div className="mt-8 flex items-center justify-center gap-4">
            <button
              type="button"
              className="rounded-xl px-5 py-2.5 text-sm font-medium text-white/90 bg-white/20 hover:bg-white/30 active:bg-white/35 backdrop-blur-md shadow transition"
              onClick={handleClick}
            >
              Sign up
            </button>

              {showPopUp && (
                <div className='bg-white rounded-sm fixed top-4 right-4 p-4 w-84 h-32 flex items-center justify-center'>
                  <p className="text-center">
                    Please send an email to the Atlas administrator {" "} 
                    (<a href="mailto:admin@example.com" className='text-blue-500 hover:underline font-medium'>
                      admin@example.com
                    </a>) {" "}
                    requesting Atlas access permission.
                  </p>
                    <button className="absolute top-2 right-2" onClick={() => setShowPopUp(false)}>
                      <img
                          src="/circle-close-multiple-svgrepo-com.svg"
                          alt="Close"
                          className="w-5 h-5 ml-2 cursor-pointer hover:opacity-70 transition"
                        />
                    </button>
                </div>
              )}

            <button
              type="button"
              onClick={() => {
                if (!isLoggedIn()) login();
                navigate("/app/dashboard");
              }}
              className="rounded-xl px-5 py-2.5 text-sm font-semibold text-white bg-white/15 hover:bg-white/25 active:bg-white/30 backdrop-blur-md shadow transition inline-flex items-center gap-2"
            >
              Login
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden>
                <path d="M8 5l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>
      </section>

      <div className="absolute inset-0 z-0 pointer-events-none">
        <div
          className="absolute w-[800px] h-[800px] rounded-full opacity-70 blur-3xl will-change-transform"
          style={{
            background: "radial-gradient(circle, rgba(255,245,245,0.95) 0%, transparent 60%)",
            animation: "float1 20s ease-in-out infinite",
            top: "-220px",
            left: "-220px",
          }}
        />
        <div
          className="absolute w-[700px] h-[700px] rounded-full opacity-80 blur-3xl will-change-transform"
          style={{
            background: "radial-gradient(circle, rgba(255,250,250,1) 0%, transparent 60%)",
            animation: "float2 18s ease-in-out infinite",
            top: "-120px",
            right: "-160px",
          }}
        />
        <div
          className="absolute w-[900px] h-[900px] rounded-full opacity-50 blur-3xl will-change-transform"
          style={{
            background: "radial-gradient(circle, rgba(220,38,38,0.6) 0%, transparent 70%)",
            animation: "float3 22s ease-in-out infinite",
            top: "22%",
            left: "30%",
          }}
        />
        <div
          className="absolute w-[600px] h-[600px] rounded-full opacity-75 blur-3xl will-change-transform"
          style={{
            background: "radial-gradient(circle, rgba(255,248,248,0.9) 0%, transparent 60%)",
            animation: "float4 16s ease-in-out infinite",
            bottom: "-160px",
            left: "10%",
          }}
        />
        <div
          className="absolute w-[750px] h-[750px] rounded-full opacity-45 blur-3xl will-change-transform"
          style={{
            background: "radial-gradient(circle, rgba(239,68,68,0.7) 0%, transparent 70%)",
            animation: "float5 19s ease-in-out infinite",
            bottom: "-210px",
            right: "15%",
          }}
        />
        <div
          className="absolute w-[650px] h-[650px] rounded-full opacity-65 blur-3xl will-change-transform"
          style={{
            background: "radial-gradient(circle, rgba(255,255,255,0.85) 0%, transparent 60%)",
            animation: "float6 17s ease-in-out infinite",
            top: "40%",
            right: "20%",
          }}
        />
      </div>

      <style>{`
        @keyframes hue { to { filter: hue-rotate(360deg) } }
        @keyframes float1 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(150px, 120px) scale(1.2); }
          66% { transform: translate(-80px, 180px) scale(0.85); }
        }
        @keyframes float2 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(-180px, 140px) scale(1.25); }
          66% { transform: translate(120px, 90px) scale(0.9); }
        }
        @keyframes float3 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(-120px, -90px) scale(1.15); }
          66% { transform: translate(150px, 130px) scale(0.88); }
        }
        @keyframes float4 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(130px, -110px) scale(1.18); }
          66% { transform: translate(-90px, -150px) scale(0.82); }
        }
        @keyframes float5 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(-150px, -120px) scale(1.12); }
          66% { transform: translate(110px, 80px) scale(0.9); }
        }
        @keyframes float6 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(-100px, 100px) scale(1.22); }
          66% { transform: translate(140px, -70px) scale(0.87); }
        }
      `}</style>
    </main>
  );
}

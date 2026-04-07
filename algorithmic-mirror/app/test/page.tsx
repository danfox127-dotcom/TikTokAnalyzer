"use client";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";

export default function TestPage() {
  const [show, setShow] = useState(true);

  return (
    <div style={{ padding: 40 }}>
      <h1 style={{ color: "red", fontSize: 24 }}>FRAMER MOTION TEST</h1>
      <motion.div
        initial={{ opacity: 1 }}
        animate={{ opacity: 1 }}
        style={{ background: "blue", color: "white", padding: 20, marginBottom: 20 }}
      >
        This motion.div should be visible
      </motion.div>
      <button onClick={() => setShow(s => !s)}>Toggle</button>
      <AnimatePresence mode="wait" initial={false}>
        {show ? (
          <motion.p key="a" initial={{ opacity: 1 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ color: "green" }}>
            GREEN TEXT (A)
          </motion.p>
        ) : (
          <motion.p key="b" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ color: "purple" }}>
            PURPLE TEXT (B)
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

import java.nio.file.*;
import java.util.*;
import java.util.regex.*;

import static org.lwjgl.glfw.GLFW.*;
import static org.lwjgl.opengl.GL33.*;

/**
 * Compiles and links Minecraft's (patched) core shaders with the real OpenGL driver, in a
 * hidden window, for each variant the game builds. Resolves #include <minecraft:x.glsl>.
 *
 * Usage: java ShaderCheck <include dir> <shader.vsh> <shader.fsh>
 */
public class ShaderCheck {
    static Path includes;

    static String resolve(String src) throws Exception {
        Matcher m = Pattern.compile("#include <minecraft:([a-z_]+\\.glsl)>").matcher(src);
        StringBuilder out = new StringBuilder();
        while (m.find()) {
            m.appendReplacement(out, Matcher.quoteReplacement(resolve(Files.readString(includes.resolve(m.group(1))))));
        }
        m.appendTail(out);
        return out.toString();
    }

    static String withDefines(String src, List<String> defines) {
        int nl = src.indexOf('\n');
        StringBuilder d = new StringBuilder();
        for (String def : defines) d.append("#define ").append(def).append('\n');
        // the #extension line must stay right after #version; put defines after it
        int nl2 = src.indexOf('\n', nl + 1);
        return src.substring(0, nl2 + 1) + d + src.substring(nl2 + 1);
    }

    static int compile(int type, String src, String label) {
        int s = glCreateShader(type);
        glShaderSource(s, src);
        glCompileShader(s);
        if (glGetShaderi(s, GL_COMPILE_STATUS) == GL_FALSE) {
            System.out.println("COMPILE FAILED " + label + ":\n" + glGetShaderInfoLog(s));
            return 0;
        }
        return s;
    }

    public static void main(String[] args) throws Exception {
        includes = Paths.get(args[0]);
        String vsh = resolve(Files.readString(Paths.get(args[1])));
        String fsh = resolve(Files.readString(Paths.get(args[2])));
        if (!glfwInit()) throw new IllegalStateException("glfw");
        glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE);
        glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
        glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
        glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
        long win = glfwCreateWindow(64, 64, "check", 0, 0);
        glfwMakeContextCurrent(win);
        org.lwjgl.opengl.GL.createCapabilities();
        System.out.println("GL " + glGetString(GL_VERSION) + " / " + glGetString(GL_RENDERER));
        List<List<String>> variants = List.of(
            List.of("ALPHA_CUTOUT 0.1"),
            List.of("ALPHA_CUTOUT 0.1", "GLINT"),
            List.of("ALPHA_CUTOUT 0.1", "OIT_ALPHA_ONLY"),
            List.of("ALPHA_CUTOUT 0.1", "OIT_ACCUMULATE"));
        boolean ok = true;
        for (List<String> v : variants) {
            int vs = compile(GL_VERTEX_SHADER, withDefines(vsh, v), "vsh " + v);
            int fs = compile(GL_FRAGMENT_SHADER, withDefines(fsh, v), "fsh " + v);
            if (vs == 0 || fs == 0) { ok = false; continue; }
            int p = glCreateProgram();
            glAttachShader(p, vs);
            glAttachShader(p, fs);
            glLinkProgram(p);
            if (glGetProgrami(p, GL_LINK_STATUS) == GL_FALSE) {
                System.out.println("LINK FAILED " + v + ":\n" + glGetProgramInfoLog(p));
                ok = false;
            } else {
                System.out.println("ok " + v);
            }
        }
        glfwTerminate();
        System.exit(ok ? 0 : 1);
    }
}

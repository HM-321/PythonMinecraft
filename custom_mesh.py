from ursina import Mesh, Vec3, Vec2


def _make_atlas_cube(top_dir='y'):
    verts = []
    uvs = []
    tris = []
    normals = []

    def add_face(v0, v1, v2, v3, uv_min, uv_max, normal,
                 flip=False, reverse_tris=False):
        base = len(verts)
        verts.extend([v0, v1, v2, v3])
        if flip:
            uvs.extend([
                Vec2(1, uv_min),
                Vec2(0, uv_min),
                Vec2(0, uv_max),
                Vec2(1, uv_max),
            ])
        else:
            uvs.extend([
                Vec2(0, uv_min),
                Vec2(1, uv_min),
                Vec2(1, uv_max),
                Vec2(0, uv_max),
            ])
        if reverse_tris:
            tris.extend([base, base + 1, base + 2,
                         base, base + 2, base + 3])
        else:
            tris.extend([base, base + 2, base + 1,
                         base, base + 3, base + 2])
        normals.extend([normal] * 4)

    UV_BOTTOM = (0.0, 1/3)
    UV_SIDE = (1/3, 2/3)
    UV_TOP = (2/3, 1.0)

    if top_dir == 'y':
        face_uvs = {
            '+y': UV_TOP, '-y': UV_BOTTOM,
            '+x': UV_SIDE, '-x': UV_SIDE,
            '+z': UV_SIDE, '-z': UV_SIDE,
        }
    elif top_dir == 'x':
        face_uvs = {
            '+x': UV_TOP, '-x': UV_BOTTOM,
            '+y': UV_SIDE, '-y': UV_SIDE,
            '+z': UV_SIDE, '-z': UV_SIDE,
        }
    elif top_dir == 'z':
        face_uvs = {
            '+z': UV_TOP, '-z': UV_BOTTOM,
            '+y': UV_SIDE, '-y': UV_SIDE,
            '+x': UV_SIDE, '-x': UV_SIDE,
        }
    else:
        face_uvs = {
            '+y': UV_TOP, '-y': UV_BOTTOM,
            '+x': UV_SIDE, '-x': UV_SIDE,
            '+z': UV_SIDE, '-z': UV_SIDE,
        }

    # +Y (上面)
    add_face(
        Vec3(-0.5, 0.5,  0.5), Vec3( 0.5, 0.5,  0.5),
        Vec3( 0.5, 0.5, -0.5), Vec3(-0.5, 0.5, -0.5),
        face_uvs['+y'][0], face_uvs['+y'][1], Vec3(0, 1, 0)
    )
    # -Y (下面) - 頂点順を反転
    add_face(
        Vec3(-0.5, -0.5, -0.5), Vec3( 0.5, -0.5, -0.5),
        Vec3( 0.5, -0.5,  0.5), Vec3(-0.5, -0.5,  0.5),
        face_uvs['-y'][0], face_uvs['-y'][1], Vec3(0, -1, 0),
        #reverse_tris=True
    )
    # +Z (前面)
    add_face(
        Vec3(-0.5, -0.5, 0.5), Vec3( 0.5, -0.5, 0.5),
        Vec3( 0.5,  0.5, 0.5), Vec3(-0.5,  0.5, 0.5),
        face_uvs['+z'][0], face_uvs['+z'][1], Vec3(0, 0, 1)
    )
    # -Z (後面)
    add_face(
        Vec3( 0.5, -0.5, -0.5), Vec3(-0.5, -0.5, -0.5),
        Vec3(-0.5,  0.5, -0.5), Vec3( 0.5,  0.5, -0.5),
        face_uvs['-z'][0], face_uvs['-z'][1], Vec3(0, 0, -1)
    )
    # +X (右面)
    add_face(
        Vec3(0.5, -0.5,  0.5), Vec3(0.5, -0.5, -0.5),
        Vec3(0.5,  0.5, -0.5), Vec3(0.5,  0.5,  0.5),
        face_uvs['+x'][0], face_uvs['+x'][1], Vec3(1, 0, 0)
    )
    # -X (左面)
    add_face(
        Vec3(-0.5, -0.5, -0.5), Vec3(-0.5, -0.5,  0.5),
        Vec3(-0.5,  0.5,  0.5), Vec3(-0.5,  0.5, -0.5),
        face_uvs['-x'][0], face_uvs['-x'][1], Vec3(-1, 0, 0)
    )

    return Mesh(vertices=verts, uvs=uvs, triangles=tris, normals=normals)


def make_face_atlas_cube(orientation='y'):
    return _make_atlas_cube(orientation)
-- SPDX-FileCopyrightText: 2024 NOI Techpark <digital@noi.bz.it>
--
-- SPDX-License-Identifier: AGPL-3.0-or-later

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS ragdata (
    id          bigserial,
    tag         text not null,
    file_name   text not null,
    start_pos   bigint,
    end_pos     bigint,
    ts          timestamp with time zone default now() not null,
    file_body   text not null,
    embedding   vector(1024) not null,
    primary key(id),
    unique(tag, file_name, start_pos, end_pos)
);

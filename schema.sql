--
-- PostgreSQL database dump
--

-- Dumped from database version 17.2
-- Dumped by pg_dump version 17.2

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: appuser
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO appuser;

--
-- Name: config_type_enum; Type: TYPE; Schema: public; Owner: appuser
--

CREATE TYPE public.config_type_enum AS ENUM (
    'initial',
    'final'
);


ALTER TYPE public.config_type_enum OWNER TO appuser;

--
-- Name: pipeline_status; Type: TYPE; Schema: public; Owner: appuser
--

CREATE TYPE public.pipeline_status AS ENUM (
    'pending',
    'running',
    'completed',
    'failed'
);


ALTER TYPE public.pipeline_status OWNER TO appuser;

--
-- Name: resource_type_enum; Type: TYPE; Schema: public; Owner: appuser
--

CREATE TYPE public.resource_type_enum AS ENUM (
    'GENOME',
    'ANNOTATION',
    'PEPTIDE'
);


ALTER TYPE public.resource_type_enum OWNER TO appuser;

--
-- Name: step_status; Type: TYPE; Schema: public; Owner: appuser
--

CREATE TYPE public.step_status AS ENUM (
    'pending',
    'running',
    'completed',
    'failed'
);


ALTER TYPE public.step_status OWNER TO appuser;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO appuser;

--
-- Name: bioprojects; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.bioprojects (
    id uuid NOT NULL,
    bioproject_id character varying(50) NOT NULL,
    description text NOT NULL,
    date_added timestamp without time zone
);


ALTER TABLE public.bioprojects OWNER TO appuser;

--
-- Name: pipeline_configs; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.pipeline_configs (
    id uuid NOT NULL,
    pipeline_id uuid,
    config_type public.config_type_enum NOT NULL,
    config_data json NOT NULL,
    config_file_path character varying NOT NULL,
    date_added timestamp without time zone
);


ALTER TABLE public.pipeline_configs OWNER TO appuser;

--
-- Name: pipeline_logs; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.pipeline_logs (
    id uuid NOT NULL,
    pipeline_id uuid,
    step_id uuid,
    logs text NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.pipeline_logs OWNER TO appuser;

--
-- Name: pipeline_resources; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.pipeline_resources (
    pipeline_id uuid NOT NULL,
    resource_id uuid NOT NULL
);


ALTER TABLE public.pipeline_resources OWNER TO appuser;

--
-- Name: pipeline_steps; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.pipeline_steps (
    id uuid NOT NULL,
    pipeline_id uuid,
    step_name character varying(100) NOT NULL,
    parameters json NOT NULL,
    requires_input_file boolean NOT NULL,
    input_files json,
    status public.step_status,
    start_time timestamp without time zone,
    end_time timestamp without time zone,
    results json,
    input_mapping json
);


ALTER TABLE public.pipeline_steps OWNER TO appuser;

--
-- Name: pipelines; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.pipelines (
    id uuid NOT NULL,
    pipeline_name character varying(100) NOT NULL,
    user_id uuid NOT NULL,
    status public.pipeline_status,
    created_at timestamp without time zone,
    start_time timestamp without time zone,
    end_time timestamp without time zone,
    notes text
);


ALTER TABLE public.pipelines OWNER TO appuser;

--
-- Name: resources; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.resources (
    id uuid NOT NULL,
    name character varying NOT NULL,
    resource_type public.resource_type_enum NOT NULL,
    species character varying,
    version character varying,
    file_path character varying NOT NULL,
    file_size integer,
    date_added timestamp without time zone,
    uploaded_by uuid NOT NULL
);


ALTER TABLE public.resources OWNER TO appuser;

--
-- Name: srr_resources; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.srr_resources (
    id uuid NOT NULL,
    bioproject_id character varying NOT NULL,
    description text NOT NULL,
    srr_id character varying NOT NULL,
    file_path text NOT NULL,
    file_size integer NOT NULL,
    date_added timestamp without time zone,
    status character varying(15) NOT NULL,
    CONSTRAINT srr_resources_status_check CHECK (((status)::text = ANY ((ARRAY['registered'::character varying, 'downloaded'::character varying, 'failed'::character varying])::text[])))
);


ALTER TABLE public.srr_resources OWNER TO appuser;

--
-- Name: users; Type: TABLE; Schema: public; Owner: appuser
--

CREATE TABLE public.users (
    username character varying NOT NULL,
    id uuid NOT NULL,
    email character varying(320) NOT NULL,
    hashed_password character varying(1024) NOT NULL,
    is_active boolean NOT NULL,
    is_superuser boolean NOT NULL,
    is_verified boolean NOT NULL
);


ALTER TABLE public.users OWNER TO appuser;

--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: bioprojects bioprojects_pkey; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.bioprojects
    ADD CONSTRAINT bioprojects_pkey PRIMARY KEY (id);


--
-- Name: pipeline_configs pipeline_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_configs
    ADD CONSTRAINT pipeline_configs_pkey PRIMARY KEY (id);


--
-- Name: pipeline_logs pipeline_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_logs
    ADD CONSTRAINT pipeline_logs_pkey PRIMARY KEY (id);


--
-- Name: pipeline_resources pipeline_resources_pkey; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_resources
    ADD CONSTRAINT pipeline_resources_pkey PRIMARY KEY (pipeline_id, resource_id);


--
-- Name: pipeline_steps pipeline_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_steps
    ADD CONSTRAINT pipeline_steps_pkey PRIMARY KEY (id);


--
-- Name: pipelines pipelines_pkey; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipelines
    ADD CONSTRAINT pipelines_pkey PRIMARY KEY (id);


--
-- Name: resources resources_pkey; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.resources
    ADD CONSTRAINT resources_pkey PRIMARY KEY (id);


--
-- Name: srr_resources srr_resources_pkey; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.srr_resources
    ADD CONSTRAINT srr_resources_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: idx_resource_type; Type: INDEX; Schema: public; Owner: appuser
--

CREATE INDEX idx_resource_type ON public.resources USING btree (resource_type);


--
-- Name: ix_bioprojects_bioproject_id; Type: INDEX; Schema: public; Owner: appuser
--

CREATE UNIQUE INDEX ix_bioprojects_bioproject_id ON public.bioprojects USING btree (bioproject_id);


--
-- Name: ix_srr_resources_bioproject_id; Type: INDEX; Schema: public; Owner: appuser
--

CREATE INDEX ix_srr_resources_bioproject_id ON public.srr_resources USING btree (bioproject_id);


--
-- Name: ix_srr_resources_file_path; Type: INDEX; Schema: public; Owner: appuser
--

CREATE INDEX ix_srr_resources_file_path ON public.srr_resources USING btree (file_path);


--
-- Name: ix_srr_resources_srr_id; Type: INDEX; Schema: public; Owner: appuser
--

CREATE UNIQUE INDEX ix_srr_resources_srr_id ON public.srr_resources USING btree (srr_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: appuser
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: pipeline_configs pipeline_configs_pipeline_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_configs
    ADD CONSTRAINT pipeline_configs_pipeline_id_fkey FOREIGN KEY (pipeline_id) REFERENCES public.pipelines(id) ON DELETE CASCADE;


--
-- Name: pipeline_logs pipeline_logs_pipeline_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_logs
    ADD CONSTRAINT pipeline_logs_pipeline_id_fkey FOREIGN KEY (pipeline_id) REFERENCES public.pipelines(id) ON DELETE CASCADE;


--
-- Name: pipeline_logs pipeline_logs_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_logs
    ADD CONSTRAINT pipeline_logs_step_id_fkey FOREIGN KEY (step_id) REFERENCES public.pipeline_steps(id) ON DELETE CASCADE;


--
-- Name: pipeline_resources pipeline_resources_pipeline_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_resources
    ADD CONSTRAINT pipeline_resources_pipeline_id_fkey FOREIGN KEY (pipeline_id) REFERENCES public.pipelines(id) ON DELETE CASCADE;


--
-- Name: pipeline_resources pipeline_resources_resource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_resources
    ADD CONSTRAINT pipeline_resources_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id) ON DELETE CASCADE;


--
-- Name: pipeline_steps pipeline_steps_pipeline_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipeline_steps
    ADD CONSTRAINT pipeline_steps_pipeline_id_fkey FOREIGN KEY (pipeline_id) REFERENCES public.pipelines(id) ON DELETE CASCADE;


--
-- Name: pipelines pipelines_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.pipelines
    ADD CONSTRAINT pipelines_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: resources resources_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.resources
    ADD CONSTRAINT resources_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: srr_resources srr_resources_bioproject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: appuser
--

ALTER TABLE ONLY public.srr_resources
    ADD CONSTRAINT srr_resources_bioproject_id_fkey FOREIGN KEY (bioproject_id) REFERENCES public.bioprojects(bioproject_id);


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO appuser;


--
-- PostgreSQL database dump complete
--

